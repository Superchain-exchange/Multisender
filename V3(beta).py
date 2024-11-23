
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
        print(f"Transaction sent with hash: {web3.to_hex(txn_hash)}")
        return txn_hash, None  # No error message

    except Exception as e:
        print(f"An error occurred while sending native currency: {str(e)}")
        return None, str(e)  # Return error message

# Function to send tokens with nonce management
def send_tokens(web3, token_contract, recipient_address, amount, chain_id, nonce):
    try:
        recipient_address = web3.to_checksum_address(recipient_address)
        token_decimals = token_contract.functions.decimals().call()
        
        # Use Decimal to avoid floating-point precision issues
        value_in_wei = int(Decimal(amount) * Decimal(10 ** token_decimals))
        
        token_balance = token_contract.functions.balanceOf(MY_ADDRESS).call()
        
        if token_balance < value_in_wei:
            print(f"Insufficient token balance for the transaction! Address: {recipient_address}")
            return False, "Insufficient token balance"  # Indicate failure due to insufficient balance
        
        # Gas details
        gas_price = web3.to_wei('1', 'gwei')
        gas_limit = 60000  # Adjusted based on average token transfer gas costs
        
        # Ensure the user has enough ETH for gas fees
        eth_balance = web3.eth.get_balance(MY_ADDRESS)
        
        if eth_balance < (gas_price * gas_limit):
            print(f"Insufficient ETH balance for gas fees! Address: {recipient_address}")
            return None, "Insufficient ETH for gas fees"  # Indicate failure due to insufficient ETH for gas
        
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
        
        return txn_hash, None  # No error message

    except Exception as e:
        print(f"An error occurred while sending tokens: {str(e)}")
        return None, str(e)  # Return error message

# Shared nonce lock for multi-threading
nonce_lock = threading.Lock()

def process_multi_transfer(web3, transfer_function, file_path, chain_id, token_contract=None):
    successful_transactions_count = 0  
    failed_transactions_count = 0  
    not_attempted_transactions_count = 0  
    
    failed_transactions_history = []  
    
    try:
        data = pd.read_excel(file_path)

        if "Amount" not in data.columns or "Receiver" not in data.columns:
            print("Excel file must have 'Amount' and 'Receiver' columns.")
            return
        
        total_amount_to_transfer = sum(data['Amount'])
        print(f"Total amount to be transferred: {total_amount_to_transfer}")

        if token_contract:
            token_balance = token_contract.functions.balanceOf(MY_ADDRESS).call()
            token_decimals = token_contract.functions.decimals().call()
            
            total_amount_in_wei = int(Decimal(total_amount_to_transfer) * Decimal(10 ** token_decimals))
            
            if token_balance < total_amount_in_wei:
                print(f"Insufficient token balance! Your balance: {token_balance / 10**token_decimals} tokens. Total transfer amount: {total_amount_to_transfer} tokens.")
                not_attempted_transactions_count += len(data)  
                return
        
        else:
            eth_balance = web3.eth.get_balance(MY_ADDRESS)
            gas_price = web3.to_wei('1', 'gwei')
            gas_limit_per_transfer = 21000 * len(data)  
            
            transaction_cost_total = gas_price * gas_limit_per_transfer
            
            if eth_balance < (transaction_cost_total + web3.to_wei(total_amount_to_transfer, 'ether')):
                print(f"Insufficient ETH balance! Your balance: {web3.from_wei(eth_balance, 'ether')} ETH. Total transfer amount with gas: {web3.from_wei(total_amount_to_transfer + transaction_cost_total, 'ether')} ETH.")
                not_attempted_transactions_count += len(data)  
                return
        
        current_nonce = web3.eth.get_transaction_count(MY_ADDRESS)
        
        results = [None] * len(data)  

        def send_transaction(index, recipient, amount):
            nonlocal current_nonce, successful_transactions_count, failed_transactions_count
            
            with nonce_lock:  
                nonce = current_nonce
                current_nonce += 1
            
            print(f"Processing transaction {index + 1} with nonce {nonce}...")
            
            txn_hash, error_message = None, None
            
            if token_contract:
                txn_hash, error_message = transfer_function(web3, token_contract, recipient, amount, chain_id, nonce)
                
            else:
                txn_hash, error_message = transfer_function(web3, recipient, amount, chain_id, nonce)

            success_status = False
            
            if txn_hash:
                try:
                    receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)  
                    
                    if receipt.status == 1:  
                        success_status = True 
                        successful_transactions_count += 1 
                    else: 
                        success_status = False 
                        failed_transactions_count += 1 
                        failed_transactions_history.append({"Recipient": recipient,
                                                             "Amount": amount,
                                                             "Reason": "Transaction failed"})  
                    
                except Exception as e:
                    print(f"An error occurred while waiting for the transaction receipt: {str(e)}")
                    failed_transactions_count += 1 
                    failed_transactions_history.append({"Recipient": recipient,
                                                         "Amount": amount,
                                                         "Reason": error_message or "Unknown error"})  

            results[index] = {"Index": index + 1,
                               "Recipient": recipient,
                               "Amount": amount,
                               "Success": success_status}

        
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
        
        sorted_results = sorted(results, key=lambda x: x["Index"]) 
        
        print("\nSummary of Transactions:")
        
        for result in sorted_results:
            status_message = "Success" if result["Success"] else "Failed"
            
            print(f"Transaction {result['Index']} - Recipient: {result['Recipient']}, Amount: {result['Amount']}, Status: {status_message}")

    finally:
         create_summary_report(successful_transactions_count,
                               failed_transactions_count,
                               not_attempted_transactions_count)

         if failed_transactions_history or not_attempted_transactions_count > 0:
             create_failed_or_not_attempted_report(failed_transactions_history)

         ask_retry_failed_transfers(failed_transactions_history)

def create_summary_report(successful_count, failed_count, not_attempted_count):
    """Prints a summary report of transaction outcomes."""
    total_transactions_count = successful_count + failed_count + not_attempted_count
    
    print("\nTransaction Summary Report:")
    print(f"Total Transactions Attempted: {total_transactions_count}")
    print(f"Successful Transactions: {successful_count}")
    print(f"Failed Transactions: {failed_count}")
    print(f"Not Attempted Transactions Due to Issues: {not_attempted_count}")

def create_failed_or_not_attempted_report(transactions_history):
    """Create an Excel report of failed or not attempted transactions."""
    # Adjusting the columns so that 'Amount' is the first column and 'Receiver' is the second
    df_failed_or_not_attempted_transactions = pd.DataFrame(transactions_history)
    
    # Rearranging columns
    if "Amount" in df_failed_or_not_attempted_transactions.columns and "Recipient" in df_failed_or_not_attempted_transactions.columns:
        df_failed_or_not_attempted_transactions = df_failed_or_not_attempted_transactions[["Amount", "Recipient", "Reason"]]
    
    num_failed_or_not_attempted_transactions = len(transactions_history)
    current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")  
    
    filename_suffix=f"{num_failed_or_not_attempted_transactions}_{current_time_str}.xlsx"
    filename=f"failed_or_not_attempted_{filename_suffix}"
    
    # Save the DataFrame to an Excel file
    df_failed_or_not_attempted_transactions.to_excel(filename, index=False)
    
    print(f"\nFailed or Not Attempted transactions report created: {filename}")


def ask_retry_failed_transfers(failed_history):
    """Ask user whether to retry sending tokens to addresses that failed."""
    
    if not failed_history:
      return
      
    retry_choice=input("\nDo you want to retry sending tokens to addresses that were unsuccessful? (y/n): ").strip().lower()
    
    if retry_choice == "y":
      for entry in failed_history:
          recipient=entry["Recipient"]
          amount=entry["Amount"]
          reason=entry["Reason"]
          print(f"\nRetrying transaction to {recipient} of amount {amount} due to '{reason}'...")
          current_nonce=web3_instance.eth.get_transaction_count(MY_ADDRESS) 
          txn_hash,_=send_tokens(web3_instance ,token_contract ,recipient ,amount ,CHAIN_ID ,current_nonce )
          if txn_hash is not None:
              print(f"Retry successful! Transaction hash: {txn_hash.hex()}")
          else:
              print("Retry failed.")
      
      print("Retry attempts completed.")

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
    
    web3_instance=initialize_web3()  
    
    if not web3_instance:
       exit(1)  
    
    MY_ADDRESS=web3_instance.eth.account.from_key(PRIVATE_KEY).address
    
    print(f"Your address: {MY_ADDRESS}")
    
    while True:
         print("\nMenu:")
         print("1. Send Native Currency (like ETH)")
         print("2. Send ERC-20 Tokens")
         print("3. Exit")
         
         choice=input("Enter your choice: ").strip()
         
         if choice == "1":
             print("\n1. Single Transfer")
             print("2. Multi-Transfer (Excel)")
             
             sub_choice=input("Enter your choice: ").strip()
             
             if sub_choice == "1":
                 try:
                     amount=float(input("Enter the amount to send: "))
                     recipient_address=input("Enter the recipient's address: ")
                     current_nonce=web3_instance.eth.get_transaction_count(MY_ADDRESS)  
                     send_native_currency(web3_instance ,recipient_address ,amount ,CHAIN_ID ,current_nonce)
                 except ValueError:
                     print("Invalid input. Please enter a valid amount and address.")
                 except Exception as e:
                     print(f"An error occurred: {str(e)}")

             elif sub_choice == "2":
                 file_path=input("Enter the path to the Excel file: ").strip()
                 process_multi_transfer(web3_instance ,send_native_currency ,file_path ,CHAIN_ID)

             else:
                 print("Invalid choice. Returning to the main menu.")

         elif choice == "2":
             token_contract=initialize_contract(web3_instance)

             print("\n1. Single Transfer")
             print("2. Multi-Transfer (Excel)")
             
             sub_choice=input("Enter your choice: ").strip()
             
             if sub_choice == "1":
                 try:
                     amount=float(input("Enter the amount to send: "))
                     recipient_address=input("Enter the recipient's address: ")
                     current_nonce=web3_instance.eth.get_transaction_count(MY_ADDRESS)  
                     send_tokens(web3_instance ,token_contract ,recipient_address ,amount ,CHAIN_ID ,current_nonce )
                 except ValueError:
                     print("Invalid input. Please enter a valid amount and address.")
                 except Exception as e:
                     print(f"An error occurred: {str(e)}")

             elif sub_choice == "2":
                 file_path=input("Enter the path to the Excel file :").strip()
                 process_multi_transfer(web3_instance ,send_tokens ,file_path ,CHAIN_ID ,token_contract)

             else:
                 print("Invalid choice. Returning to the main menu.")

         elif choice == "3":
             print("Exiting the script. Goodbye!")
             break

         else:
             print("Invalid choice. Please try again.")
