from web3 import Web3
import pandas as pd
import threading
import time
from decimal import Decimal, getcontext

# Increase decimal precision for small values
getcontext().prec = 50  # Set precision to handle small decimals

# Initialize Web3 connection
def initialize_web3():
    while True:
        try:
            rpc_url = input("Enter the RPC URL (e.g., https://rpc.minato.soneium.org/): ").strip()
            chain_id = int(input("Enter the Chain ID (e.g., 1946 for Soneium Minato Testnet): ").strip())
            explorer_url = input("Enter the Blockchain Explorer URL (optional, press Enter to skip): ").strip()

            web3_instance = Web3(Web3.HTTPProvider(rpc_url))
            if not web3_instance.is_connected():
                print("Failed to connect to the blockchain. Please check the RPC URL.")
                continue

            print("Connected to the blockchain successfully!")
            return web3_instance, chain_id, explorer_url
        except ValueError:
            print("Invalid input. Please enter valid values for RPC URL, Chain ID, and Blockchain Explorer.")
        except Exception as e:
            print(f"An error occurred: {str(e)}. Please try again.")

# Function to initialize the ERC-20 contract
def initialize_contract(web3):
    while True:
        try:
            contract_address = input("Enter the ERC-20 token contract address: ").strip()
            if not web3.is_checksum_address(contract_address):
                contract_address = web3.to_checksum_address(contract_address)

            # Initialize the contract
            token_contract = web3.eth.contract(address=contract_address, abi=contract_abi)

            # Test the contract by calling a simple function
            token_decimals = token_contract.functions.decimals().call()
            print(f"Contract initialized successfully! Token Decimals: {token_decimals}")
            return token_contract
        except Exception as e:
            print(f"Invalid contract address. Error: {e}. Please try again.")

# Function to send native currency (e.g., ETH) with nonce management
def send_native_currency(web3, recipient_address, amount, chain_id, nonce):
    try:
        recipient_address = web3.to_checksum_address(recipient_address)
        value_in_wei = web3.to_wei(amount, 'ether')
        eth_balance = web3.eth.get_balance(MY_ADDRESS)

        # Gas details
        gas_price = web3.to_wei('1', 'gwei')
        gas_limit = 21000
        transaction_cost = gas_price * gas_limit

        if eth_balance < (transaction_cost + value_in_wei):
            print(f"Insufficient ETH balance for the transaction! Address: {recipient_address}")
            return False

        # Build and sign the transaction
        txn = {
            'to': recipient_address,
            'value': value_in_wei,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': chain_id
        }
        signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

        print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")
        return txn_hash

    except Exception as e:
        print(f"An error occurred while sending native currency: {str(e)}")
        return None

# Function to send tokens with nonce management
def send_tokens(web3, token_contract, recipient_address, amount, chain_id, nonce):
    try:
        recipient_address = web3.to_checksum_address(recipient_address)
        token_decimals = token_contract.functions.decimals().call()

        # Use Decimal to avoid floating-point precision issues
        value_in_wei = int(Decimal(amount) * Decimal(10 ** token_decimals))  # Scale and convert to int
        token_balance = token_contract.functions.balanceOf(MY_ADDRESS).call()

        if token_balance < value_in_wei:
            print(f"Insufficient token balance for the transaction! Address: {recipient_address}")
            return False

        # Gas details
        gas_price = web3.to_wei('1', 'gwei')
        gas_limit = 60000  # Adjusted based on average token transfer gas costs
        transaction_cost = gas_price * gas_limit

        # Ensure the user has enough ETH for gas fees
        eth_balance = web3.eth.get_balance(MY_ADDRESS)
        if eth_balance < transaction_cost:
            print(f"Insufficient ETH balance for gas fees! Address: {recipient_address}")
            return None

        # Build and sign the transaction
        txn = token_contract.functions.transfer(recipient_address, value_in_wei).build_transaction({
            'chainId': chain_id,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
        })
        signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

        print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")
        return txn_hash

    except Exception as e:
        print(f"An error occurred while sending tokens: {str(e)}")
        return None

# Shared nonce lock for multi-threading
nonce_lock = threading.Lock()

def process_multi_transfer(web3, transfer_function, file_path, chain_id, token_contract=None):
    try:
        data = pd.read_excel(file_path)

        if "Amount" not in data.columns or "Receiver" not in data.columns:
            print("Excel file must have 'Amount' and 'Receiver' columns.")
            return

        # Calculate the total amount to be transferred
        total_amount = sum(data['Amount'])
        print(f"Total amount to be transferred: {total_amount}")

        # Check the user's balance (ETH or Token)
        if token_contract:
            token_balance = token_contract.functions.balanceOf(MY_ADDRESS).call()
            token_decimals = token_contract.functions.decimals().call()
            total_amount_in_wei = int(Decimal(total_amount) * Decimal(10 ** token_decimals))

            if token_balance < total_amount_in_wei:
                print(f"Insufficient token balance! Your balance: {token_balance / 10**token_decimals} tokens. Total transfer amount: {total_amount} tokens.")
                return  # Abort transfer if balance is insufficient
        else:
            eth_balance = web3.eth.get_balance(MY_ADDRESS)
            gas_price = web3.to_wei('1', 'gwei')
            gas_limit = 21000 * len(data)  # Estimate based on number of transfers
            transaction_cost = gas_price * gas_limit

            if eth_balance < (transaction_cost + web3.to_wei(total_amount, 'ether')):
                print(f"Insufficient ETH balance! Your balance: {web3.from_wei(eth_balance, 'ether')} ETH. Total transfer amount with gas: {web3.from_wei(total_amount + transaction_cost, 'ether')} ETH.")
                return  # Abort transfer if balance is insufficient

        # Start nonce from the current account's transaction count
        current_nonce = web3.eth.get_transaction_count(MY_ADDRESS)
        results = [None] * len(data)  # Pre-allocate list to store results in correct order

        # Thread worker function
        def send_transaction(index, recipient, amount):
            nonlocal current_nonce
            with nonce_lock:  # Ensure only one thread updates the nonce at a time
                nonce = current_nonce
                current_nonce += 1

            print(f"Processing transaction {index + 1} with nonce {nonce}...")
            txn_hash = None
            if token_contract:
                txn_hash = transfer_function(web3, token_contract, recipient, amount, chain_id, nonce)
            else:
                txn_hash = transfer_function(web3, recipient, amount, chain_id, nonce)

            success = False
            if txn_hash:
                try:
                    # Wait for the transaction to be mined
                    receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)  # Wait up to 5 minutes
                    if receipt.status == 1:  # status 1 means success
                        success = True
                    else:
                        success = False
                        print(f"Transaction failed: {txn_hash.hex()}")
                except Exception as e:
                    print(f"An error occurred while waiting for the transaction receipt: {str(e)}")

            # Store the result in the correct order
            results[index] = {"Index": index + 1, "Recipient": recipient, "Amount": amount, "Success": success}

        # Create and start threads
        threads = []
        for index, row in data.iterrows():
            recipient = row['Receiver']
            amount = row['Amount']
            thread = threading.Thread(target=send_transaction, args=(index, recipient, amount))
            threads.append(thread)
            thread.start()
            time.sleep(0.2)  # Prevent nonce conflicts by staggering threads

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Sort results by the original index to ensure they are displayed in correct order
        sorted_results = sorted(results, key=lambda x: x["Index"])

        # Print results
        print("\nSummary of Transactions:")
        for result in sorted_results:
            status = "Success" if result["Success"] else "Failed"
            print(f"Transaction {result['Index']} - Recipient: {result['Recipient']}, Amount: {result['Amount']}, Status: {status}")

    except FileNotFoundError:
        print("Excel file not found. Please check the file path.")
    except Exception as e:
        print(f"An error occurred while processing the Excel file: {str(e)}")

# ERC-20 Token ABI
contract_abi = [
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

# Main Execution
if __name__ == "__main__":
    print("Welcome to the Token and Native Currency Transfer Script!")

    web3, chain_id, explorer_url = initialize_web3()
    PRIVATE_KEY = input("Enter your private key: ").strip()
    MY_ADDRESS = web3.eth.account.from_key(PRIVATE_KEY).address
    print(f"Your address: {MY_ADDRESS}")

    while True:
        print("\nMenu:")
        print("1. Send Native Currency (like ETH, BNB, AVAX)")
        print("2. Send ERC-20 Tokens")
        print("3. Exit")

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            print("\n1. Single Transfer")
            print("2. Multi-Transfer (Excel)")
            sub_choice = input("Enter your choice: ").strip()

            if sub_choice == "1":
                try:
                    amount = float(input("Enter the amount to send: "))
                    recipient_address = input("Enter the recipient's address: ")
                    send_native_currency(web3, recipient_address, amount, chain_id, current_nonce)
                except ValueError:
                    print("Invalid input. Please enter a valid amount and address.")
                except Exception as e:
                    print(f"An error occurred: {str(e)}")

            elif sub_choice == "2":
                file_path = input("Enter the path to the Excel file: ").strip()
                process_multi_transfer(web3, send_native_currency, file_path, chain_id)

            else:
                print("Invalid choice. Returning to the main menu.")

        elif choice == "2":
            token_contract = initialize_contract(web3)
            print("\n1. Single Transfer")
            print("2. Multi-Transfer (Excel)")
            sub_choice = input("Enter your choice: ").strip()

            if sub_choice == "1":
                try:
                    amount = float(input("Enter the amount to send: "))
                    recipient_address = input("Enter the recipient's address: ")
                    send_tokens(web3, token_contract, recipient_address, amount, chain_id, current_nonce)
                except ValueError:
                    print("Invalid input. Please enter a valid amount and address.")
                except Exception as e:
                    print(f"An error occurred: {str(e)}")

            elif sub_choice == "2":
                file_path = input("Enter the path to the Excel file: ").strip()
                process_multi_transfer(web3, send_tokens, file_path, chain_id, token_contract)

            else:
                print("Invalid choice. Returning to the main menu.")

        elif choice == "3":
            print("Exiting the script. Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")
