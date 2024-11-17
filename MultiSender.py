from web3 import Web3
import pandas as pd
import time

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

# Function to send native currency (e.g., ETH)
def send_native_currency(web3, recipient_address, amount, chain_id):
    try:
        recipient_address = web3.to_checksum_address(recipient_address)
        value_in_wei = web3.to_wei(amount, 'ether')
        eth_balance = web3.eth.get_balance(MY_ADDRESS)

        # Gas details
        gas_price = web3.to_wei('0.51', 'gwei')
        gas_limit = 21000
        transaction_cost = gas_price * gas_limit

        if eth_balance < (transaction_cost + value_in_wei):
            print("Insufficient ETH balance for the transaction!")
            return False

        # Build and sign the transaction
        txn = {
            'to': recipient_address,
            'value': value_in_wei,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': web3.eth.get_transaction_count(MY_ADDRESS),
            'chainId': chain_id
        }
        signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

        print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=120)
        if receipt.status == 1:
            print(f"Transaction confirmed! Hash: {web3.to_hex(txn_hash)}")
            return True
        else:
            print(f"Transaction failed! Hash: {web3.to_hex(txn_hash)}")
            return False

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

# Function to send tokens
def send_tokens(web3, token_contract, recipient_address, amount, chain_id):
    try:
        recipient_address = web3.to_checksum_address(recipient_address)
        value_in_wei = web3.to_wei(amount, 'ether')
        eth_balance = web3.eth.get_balance(MY_ADDRESS)

        # Gas details
        gas_price = web3.to_wei('0.51', 'gwei')
        gas_limit = 40000
        transaction_cost = gas_price * gas_limit

        if eth_balance < transaction_cost:
            print("Insufficient ETH balance for gas fees!")
            return False

        # Build and sign the transaction
        txn = token_contract.functions.transfer(recipient_address, value_in_wei).build_transaction({
            'chainId': chain_id,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': web3.eth.get_transaction_count(MY_ADDRESS),
        })
        signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

        print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=120)
        if receipt.status == 1:
            print(f"Transaction confirmed! Hash: {web3.to_hex(txn_hash)}")
            return True
        else:
            print(f"Transaction failed! Hash: {web3.to_hex(txn_hash)}")
            return False

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

# Function to process multi-transfers from Excel
def process_multi_transfer(web3, transfer_function, file_path, chain_id, token_contract=None):
    try:
        data = pd.read_excel(file_path)

        if "Amount" not in data.columns or "Receiver" not in data.columns:
            print("Excel file must have 'Amount' and 'Receiver' columns.")
            return

        for index, row in data.iterrows():
            amount = row['Amount']
            recipient = row['Receiver']

            print(f"\nProcessing transaction {index + 1}:")
            print(f"Amount: {amount}, Receiver: {recipient}")

            if token_contract:
                success = transfer_function(web3, token_contract, recipient, amount, chain_id)
            else:
                success = transfer_function(web3, recipient, amount, chain_id)

            if not success:
                print("Transaction failed. Stopping further transactions.")
                break

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
        print("1. Send Native Currency (like ETH , BNB , AVAX )")
        print("2. Send ERC-20 Tokens ")
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
                    send_native_currency(web3, recipient_address, amount, chain_id)
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
                    send_tokens(web3, token_contract, recipient_address, amount, chain_id)
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
