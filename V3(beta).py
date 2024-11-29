from dotenv import load_dotenv
import os
from web3 import Web3
import pandas as pd
import threading
import time
from decimal import Decimal, getcontext
from datetime import datetime

# Increase decimal precision for small values
getcontext().prec = 50

# Load environment variables from .env file
load_dotenv()

# Retrieve values from environment variables
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
RPC_URL = os.getenv('RPC_URL')
CHAIN_ID = int(os.getenv('CHAIN_ID'))
EXPLORER_URL = os.getenv('EXPLORER_URL')

# Initialize Web3 connection with retry logic
def initialize_web3():
    for attempt in range(5):  # Try up to 5 times
        try:
            rpc_url = input("Enter the RPC URL (e.g., https://rpc.minato.soneium.org/): ").strip()
            web3_instance = Web3(Web3.HTTPProvider(rpc_url))
            if not web3_instance.is_connected():
                print(f"Attempt {attempt + 1}: Failed to connect to the blockchain. Please check the RPC URL.")
                time.sleep(2)  # Wait before retrying
                continue
            print("Connected to the blockchain successfully!")
            return web3_instance
        except Exception as e:
            print(f"Attempt {attempt + 1}: An error occurred: {str(e)}. Retrying...")
            time.sleep(2)  # Wait before retrying

    print("Failed to connect after several attempts.")
    return None

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
def send_native_currency(web3, recipient_address, amount, chain_id, nonce, silent=False):
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
            return False, "Insufficient ETH balance"

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
        if not silent:
            print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")
            print("Waiting for transaction confirmation...")
        
        receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)
        
        if not silent:
            if receipt['status'] == 1:
                print("Transaction successful! 🟢")
                print(f"Transaction explorer URL: {EXPLORER_URL}/tx/{web3.to_hex(txn_hash)}")
            else:
                print("Transaction failed! 🔴")
                print(f"Check transaction: {EXPLORER_URL}/tx/{web3.to_hex(txn_hash)}")
        
        return txn_hash, None

    except Exception as e:
        print(f"An error occurred while sending native currency: {str(e)}")
        return None, str(e)

# Function to send tokens with nonce management
def send_tokens(web3, token_contract, recipient_address, amount, chain_id, nonce, silent=False):
    try:
        recipient_address = web3.to_checksum_address(recipient_address)
        token_decimals = token_contract.functions.decimals().call()
        
        value_in_wei = int(Decimal(amount) * Decimal(10 ** token_decimals))
        token_balance = token_contract.functions.balanceOf(MY_ADDRESS).call()
        
        if token_balance < value_in_wei:
            print(f"Insufficient token balance for the transaction! Address: {recipient_address}")
            return False, "Insufficient token balance"
        
        # Gas details
        gas_price = web3.to_wei('1', 'gwei')
        gas_limit = 60000
        
        eth_balance = web3.eth.get_balance(MY_ADDRESS)
        
        if eth_balance < (gas_price * gas_limit):
            print(f"Insufficient ETH balance for gas fees! Address: {recipient_address}")
            return None, "Insufficient ETH for gas fees"
        
        txn = token_contract.functions.transfer(recipient_address, value_in_wei).build_transaction({
            'chainId': chain_id,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
        })
        
        signed_txn = web3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        if not silent:
            print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")
            print("Waiting for transaction confirmation...")
        
        receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)
        
        if not silent:
            if receipt['status'] == 1:
                print("Transaction successful! 🟢")
                print(f"Transaction explorer URL: {EXPLORER_URL}/tx/{web3.to_hex(txn_hash)}")
            else:
                print("Transaction failed! 🔴")
                print(f"Check transaction: {EXPLORER_URL}/tx/{web3.to_hex(txn_hash)}")
        
        return txn_hash, None

    except Exception as e:
        print(f"An error occurred while sending tokens: {str(e)}")
        return None, str(e)

# Shared nonce lock for multi-threading
nonce_lock = threading.Lock()

def process_multi_transfer(web3, transfer_function, file_path, chain_id, token_contract=None):
    successful_transactions_count = 0
    failed_transactions_count = 0
    not_attempted_transactions_count = 0
    initiated_transactions_count = 0
    failed_transactions_history = []
    current_nonce = web3.eth.get_transaction_count(MY_ADDRESS)
    nonce_lock = threading.Lock()
    initiated_lock = threading.Lock()
    status_lock = threading.Lock()
    
    def update_progress(current_initiated, total_transactions):
        current_display = min(current_initiated, total_transactions)
        print(f"\rProcessing transaction {current_display}/{total_transactions} | "
              f"Successful: {successful_transactions_count}/{total_transactions} | "
              f"Failed: {failed_transactions_count}/{total_transactions}", end="", flush=True)

    def send_transaction(index, recipient, amount):
        nonlocal current_nonce, successful_transactions_count, failed_transactions_count, initiated_transactions_count
        total_transactions = len(data)
        
        try:
            # First increment initiated count and update display
            with initiated_lock:
                initiated_transactions_count += 1
                current_initiated = initiated_transactions_count
                update_progress(current_initiated, total_transactions)

            with nonce_lock:
                nonce = current_nonce
                current_nonce += 1

            if token_contract:
                txn_hash, error = transfer_function(web3, token_contract, recipient, amount, chain_id, nonce, silent=True)
            else:
                txn_hash, error = transfer_function(web3, recipient, amount, chain_id, nonce, silent=True)

            if txn_hash:
                # Wait for transaction receipt
                receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)
                success = receipt['status'] == 1
                
                # Update success/failed count immediately after transaction completes
                with status_lock:
                    if success:
                        successful_transactions_count += 1
                    else:
                        failed_transactions_count += 1
                    update_progress(initiated_transactions_count, total_transactions)

                transactions.append({
                    'index': index + 1,
                    'recipient': recipient,
                    'amount': amount,
                    'status': 'Success' if success else 'Failed',
                    'hash': web3.to_hex(txn_hash),
                    'explorer_url': f"{EXPLORER_URL}/tx/{web3.to_hex(txn_hash)}"
                })
            else:
                # Update failed count immediately if transaction wasn't sent
                with status_lock:
                    failed_transactions_count += 1
                    update_progress(initiated_transactions_count, total_transactions)
                transactions.append({
                    'index': index + 1,
                    'recipient': recipient,
                    'amount': amount,
                    'status': 'Failed',
                    'hash': 'N/A',
                    'explorer_url': 'N/A',
                    'error': error
                })

        except Exception as e:
            # Update failed count immediately on exception
            with status_lock:
                failed_transactions_count += 1
                update_progress(initiated_transactions_count, total_transactions)
            transactions.append({
                'index': index + 1,
                'recipient': recipient,
                'amount': amount,
                'status': 'Failed',
                'hash': 'N/A',
                'explorer_url': 'N/A',
                'error': str(e)
            })

    try:
        data = pd.read_excel(file_path)
        if "Amount" not in data.columns or "Receiver" not in data.columns:
            print("Excel file must have 'Amount' and 'Receiver' columns.")
            return

        total_amount_to_transfer = sum(data['Amount'])
        
        # Show transfer details and ask for confirmation
        if token_contract:
            token_symbol = token_contract.functions.symbol().call()
            print(f"\nTotal amount to be transferred: {total_amount_to_transfer} {token_symbol}")
        else:
            print(f"\nTotal amount to be transferred: {total_amount_to_transfer} ETH")
            
        print("\nDo you want to proceed?")
        print("1. Yes")
        print("2. No")
        
        confirm = input("Enter your choice (1 or 2): ").strip()
        if confirm != "1":
            print("Transaction cancelled by user.")
            return

        transactions = []

        threads = []
        
        for index, row in data.iterrows():
            recipient = row['Receiver']
            amount = row['Amount']
            
            thread = threading.Thread(target=send_transaction,
                                      args=(index,
                                            recipient,
                                            amount))
            
            threads.append(thread)
            
            thread.start()
            
            time.sleep(0.2)  
        
        for thread in threads:
            thread.join()  
        
        # After all threads complete
        print("\n")  # Move to new line after progress display
        print("\nSummary of Transactions:")
        sorted_transactions = sorted(transactions, key=lambda x: x['index'])
        for tx in sorted_transactions:
            status_emoji = "🟢" if tx['status'] == 'Success' else "🔴"
            print(f"Transaction {tx['index']} - "
                  f"Recipient: {tx['recipient']}, "
                  f"Amount: {tx['amount']}, "
                  f"Status: {tx['status']} {status_emoji}, "
                  f"Hash: {tx['hash']}")

        print(f"\nTotal Transactions: {len(data)}")
        print(f"Successful: {successful_transactions_count}")
        print(f"Failed: {failed_transactions_count}")
        print(f"Not Attempted: {not_attempted_transactions_count}")

        # Ask user about exporting summary
        print("\nWould you like to export the transaction summary to an Excel file?")
        print("1. No")
        print("2. Export all transactions")
        print("3. Export only failed transactions")
        
        export_choice = input("Enter your choice (1-3): ").strip()
        
        if export_choice in ['2', '3']:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Prepare data for export
            export_data = []
            for tx in sorted_transactions:
                if export_choice == '2' or (export_choice == '3' and tx['status'] == 'Failed'):
                    export_data.append({
                        'Amount': tx['amount'],
                        'Receiver': tx['recipient'],
                        'Status': tx['status'],
                        'Hash': tx['hash']
                    })
            
            if export_data:
                # Create DataFrame and export to Excel
                df = pd.DataFrame(export_data)
                
                # Generate filename based on choice
                filename = f"transaction_summary_{timestamp}.xlsx" if export_choice == '2' else f"failed_transactions_{timestamp}.xlsx"
                
                df.to_excel(filename, index=False)
                print(f"\nSummary exported to: {filename}")
            else:
                if export_choice == '3':
                    print("\nNo failed transactions to export.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if failed_transactions_count > 0:
            print("\nFailed Transactions Details:")
            for tx in sorted_transactions:
                if tx['status'] == 'Failed':
                    print(f"Recipient: {tx['recipient']}")
                    print(f"Amount: {tx['amount']}")
                    print(f"Error: {tx.get('error', 'Unknown error')}")
                    print("---")

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
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

# Main Execution 
if __name__ == "__main__":
    print("Welcome to the Token and Native Currency Transfer Script!")
    
    web3_instance = initialize_web3()  
    
    if not web3_instance:
        exit(1)  
    
    MY_ADDRESS = web3_instance.eth.account.from_key(PRIVATE_KEY).address
    print(f"Your address: {MY_ADDRESS}")
    
    while True:
        print("\nMain Menu:")
        print("1. Send Native Currency (like ETH)")
        print("2. Send ERC-20 Tokens")
        print("3. Exit")
        
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            while True:  # Loop for native currency submenu
                # Show ETH balance immediately after selecting native currency
                eth_balance = web3_instance.eth.get_balance(MY_ADDRESS)
                eth_balance_in_eth = web3_instance.from_wei(eth_balance, 'ether')
                print(f"\nYour current ETH balance: {eth_balance_in_eth} ETH")
                
                print("\nNative Currency Transfer Menu:")
                print("1. Single Transfer")
                print("2. Multi-Transfer (Excel)")
                print("3. Back to Main Menu")
                
                sub_choice = input("Enter your choice: ").strip()
                
                if sub_choice == "3":  # Back to main menu
                    break
                
                elif sub_choice == "1":
                    try:
                        amount = float(input("Enter the amount to send: "))
                        recipient_address = input("Enter the recipient's address: ")
                        
                        # Show transfer details and ask for confirmation
                        print(f"\nAmount to be transferred: {amount} ETH")
                        print("\nDo you want to proceed?")
                        print("1. Yes")
                        print("2. No")
                        
                        confirm = input("Enter your choice (1 or 2): ").strip()
                        if confirm == "1":
                            current_nonce = web3_instance.eth.get_transaction_count(MY_ADDRESS)
                            send_native_currency(web3_instance, recipient_address, amount, CHAIN_ID, current_nonce)
                        else:
                            print("Transaction cancelled by user.")
                            
                    except ValueError:
                        print("Invalid input. Please enter a valid amount and address.")
                    except Exception as e:
                        print(f"An error occurred: {str(e)}")

                elif sub_choice == "2":
                    file_path = input("Enter the path to the Excel file: ").strip()
                    # Remove quotes if present at start and end
                    file_path = file_path.strip('"')
                    process_multi_transfer(web3_instance, send_native_currency, file_path, CHAIN_ID)

                else:
                    print("Invalid choice. Please try again.")

        elif choice == "2":
            while True:  # Loop for token submenu
                token_contract = initialize_contract(web3_instance)
                
                # Show token balance immediately after contract initialization
                try:
                    token_balance = token_contract.functions.balanceOf(MY_ADDRESS).call()
                    token_decimals = token_contract.functions.decimals().call()
                    token_symbol = token_contract.functions.symbol().call()
                    token_balance_formatted = token_balance / 10**token_decimals
                    print(f"\nYour current {token_symbol} balance: {token_balance_formatted} {token_symbol}")
                except Exception as e:
                    print(f"Error fetching token balance: {str(e)}")
                
                print("\nToken Transfer Menu:")
                print("1. Single Transfer")
                print("2. Multi-Transfer (Excel)")
                print("3. Back to Main Menu")
                
                sub_choice = input("Enter your choice: ").strip()
                
                if sub_choice == "3":  # Back to main menu
                    break
                
                elif sub_choice == "1":
                    try:
                        amount = float(input("Enter the amount to send: "))
                        recipient_address = input("Enter the recipient's address: ")
                        
                        # Show transfer details and ask for confirmation
                        token_symbol = token_contract.functions.symbol().call()
                        print(f"\nAmount to be transferred: {amount} {token_symbol}")
                        print("\nDo you want to proceed?")
                        print("1. Yes")
                        print("2. No")
                        
                        confirm = input("Enter your choice (1 or 2): ").strip()
                        if confirm == "1":
                            current_nonce = web3_instance.eth.get_transaction_count(MY_ADDRESS)
                            send_tokens(web3_instance, token_contract, recipient_address, amount, CHAIN_ID, current_nonce)
                        else:
                            print("Transaction cancelled by user.")
                            
                    except ValueError:
                        print("Invalid input. Please enter a valid amount and address.")
                    except Exception as e:
                        print(f"An error occurred: {str(e)}")

                elif sub_choice == "2":
                    file_path = input("Enter the path to the Excel file: ").strip()
                    # Remove quotes if present at start and end
                    file_path = file_path.strip('"')
                    process_multi_transfer(web3_instance, send_tokens, file_path, CHAIN_ID, token_contract)

                else:
                    print("Invalid choice. Please try again.")

        elif choice == "3":
            print("Exiting the script. Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")
