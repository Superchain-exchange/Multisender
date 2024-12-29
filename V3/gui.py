import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from PIL import Image, ImageTk
import threading
from decimal import Decimal, getcontext
import pandas as pd
import os
from dotenv import load_dotenv
from web3 import Web3
import time
from datetime import datetime
import queue

# Increase decimal precision for small values
getcontext().prec = 50

# Set appearance mode and default color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ERC-20 Token ABI (from your original code)
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

class TokenTransferApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Load environment variables
        load_dotenv()
        self.PRIVATE_KEY = os.getenv('PRIVATE_KEY')
        self.RPC_URL = os.getenv('RPC_URL')
        self.CHAIN_ID = int(os.getenv('CHAIN_ID'))
        self.EXPLORER_URL = os.getenv('EXPLORER_URL')
        
        # Initialize web3 and contract variables
        self.web3 = None
        self.token_contract = None
        self.MY_ADDRESS = None
        self.processing_queue = queue.Queue()
        
        # Setup main window
        self.title("Blockchain Token Transfer")
        self.geometry("1400x900")
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Initialize UI
        self.setup_ui()
        
        # Start web3 connection
        self.initialize_web3()

        self.after(100, self.process_queue)
    
    def process_queue(self):
        try:
            message = self.processing_queue.get_nowait()
            self.log_message(message)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def setup_ui(self):
        # Configure main container grid
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)
        
        # Header
        self.header = ctk.CTkFrame(self.main_container)
        self.header.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.title_label = ctk.CTkLabel(
            self.header, 
            text="Blockchain Token Transfer", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=10)
        
        # Connection status
        self.status_frame = ctk.CTkFrame(self.header)
        self.status_frame.pack(fill="x", padx=10, pady=5)
        
        self.connection_status = ctk.CTkLabel(
            self.status_frame, 
            text="Not Connected",
            font=ctk.CTkFont(size=12)
        )
        self.connection_status.pack(side="left", padx=5)
        
        self.address_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.address_label.pack(side="right", padx=5)
        
        # Progress bar and status
        self.progress_frame = ctk.CTkFrame(self.status_frame)
        self.progress_frame.pack(fill="x", pady=5)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", padx=10)
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="")
        self.progress_label.pack()
        
        # Hide progress initially
        self.progress_frame.pack_forget()
        
        # Main content area
        self.content = ctk.CTkFrame(self.main_container)
        self.content.grid(row=1, column=0, sticky="nsew", padx=10)
        
        # Tabview for Native and Token Transfers
        self.tabview = ctk.CTkTabview(self.content, width=1100)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        self.tabview.add("Native Currency")
        self.tabview.add("ERC-20 Tokens")
        
        # Native Currency tab UI
        self.create_native_currency_tab()
        
        # ERC-20 Tokens tab UI
        self.create_token_transfer_tab()
        
        # Create console output
        self.create_console_output()
    
    def create_native_currency_tab(self):
        native_tab = self.tabview.tab("Native Currency")
        native_tab.grid_columnconfigure(0, weight=1)

        # Balance display
        self.native_balance_label = ctk.CTkLabel(
            native_tab,
            text="Current Balance: 0 ETH",
            font=ctk.CTkFont(size=16)
        )
        self.native_balance_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")

        # Input fields
        self.native_amount_entry = ctk.CTkEntry(
            native_tab,
            placeholder_text="Amount (ETH)",
            width=300
        )
        self.native_amount_entry.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        
        self.native_recipient_entry = ctk.CTkEntry(
            native_tab,
            placeholder_text="Recipient Address",
            width=300
        )
        self.native_recipient_entry.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        
        # Buttons
        self.native_single_transfer_btn = ctk.CTkButton(
            native_tab,
            text="Single Transfer",
            command=self.native_single_transfer,
            width=200
        )
        self.native_single_transfer_btn.grid(row=3, column=0, padx=20, pady=10, sticky="w")
        
        self.native_multi_transfer_btn = ctk.CTkButton(
            native_tab,
            text="Multi-Transfer (Excel)",
            command=self.native_multi_transfer,
            width=200
        )
        self.native_multi_transfer_btn.grid(row=4, column=0, padx=20, pady=10, sticky="w")

    def create_token_transfer_tab(self):
        token_tab = self.tabview.tab("ERC-20 Tokens")
        token_tab.grid_columnconfigure(0, weight=1)

        # Contract address input
        self.contract_address_entry = ctk.CTkEntry(
            token_tab,
            placeholder_text="Contract Address",
            width=300
        )
        self.contract_address_entry.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.initialize_contract_btn = ctk.CTkButton(
            token_tab,
            text="Initialize Contract",
            command=self.initialize_contract,
            width=200
        )
        self.initialize_contract_btn.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        
        # Token info label
        self.token_info_label = ctk.CTkLabel(
            token_tab,
            text="Token Balance: N/A",
            font=ctk.CTkFont(size=16)
        )
        self.token_info_label.grid(row=2, column=0, padx=20, pady=20, sticky="w")
        
        # Contract Symbol label
        self.token_symbol_label = ctk.CTkLabel(
            token_tab,
            text="Token Symbol: N/A",
            font=ctk.CTkFont(size=16)
        )
        self.token_symbol_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")

        # Transfer inputs
        self.token_amount_entry = ctk.CTkEntry(
            token_tab,
            placeholder_text="Amount",
            width=300
        )
        self.token_amount_entry.grid(row=4, column=0, padx=20, pady=10, sticky="w")
        
        self.token_recipient_entry = ctk.CTkEntry(
            token_tab,
            placeholder_text="Recipient Address",
            width=300
        )
        self.token_recipient_entry.grid(row=5, column=0, padx=20, pady=10, sticky="w")
        
        # Buttons
        self.token_single_transfer_btn = ctk.CTkButton(
            token_tab,
            text="Single Transfer",
            command=self.token_single_transfer,
            width=200
        )
        self.token_single_transfer_btn.grid(row=6, column=0, padx=20, pady=10, sticky="w")
        
        self.token_multi_transfer_btn = ctk.CTkButton(
            token_tab,
            text="Multi-Transfer (Excel)",
            command=self.token_multi_transfer,
            width=200
        )
        self.token_multi_transfer_btn.grid(row=7, column=0, padx=20, pady=10, sticky="w")

    def create_console_output(self):
        self.console_frame = ctk.CTkFrame(self.main_container)
        self.console_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        self.console_text = ctk.CTkTextbox(self.console_frame, height=150)
        self.console_text.pack(fill="both", expand=True)
    
    def log_message(self, message):
        self.console_text.insert("end", f"{message}\n")
        self.console_text.see("end")
        self.update_idletasks()

    # Function implementations from your original code, adapted for GUI
    def initialize_web3(self):
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.RPC_URL))
            if self.web3.is_connected():
                self.MY_ADDRESS = self.web3.eth.account.from_key(self.PRIVATE_KEY).address
                self.connection_status.configure(text="Connected 🟢")
                self.address_label.configure(text=f"Address: {self.MY_ADDRESS[:6]}...{self.MY_ADDRESS[-4:]}")
                self.update_native_balance()
                self.processing_queue.put("Connected to the blockchain successfully!")
                return True
            else:
                self.connection_status.configure(text="Connection Failed 🔴")
                self.processing_queue.put("Connection Failed!")
                return False
        except Exception as e:
            self.connection_status.configure(text="Connection Error 🔴")
            self.processing_queue.put(f"Connection Error: {str(e)}")
            return False
    
    def initialize_contract(self):
        contract_address = self.contract_address_entry.get().strip()
        if not self.web3:
            self.processing_queue.put("Connect to the blockchain first.")
            return
        try:
            if not self.web3.is_checksum_address(contract_address):
               contract_address = self.web3.to_checksum_address(contract_address)
            self.token_contract = self.web3.eth.contract(address=contract_address, abi=contract_abi)
            token_decimals = self.token_contract.functions.decimals().call()
            token_symbol = self.token_contract.functions.symbol().call()
            self.processing_queue.put(f"Contract initialized successfully! Token Decimals: {token_decimals}")
            self.token_symbol_label.configure(text=f"Token Symbol: {token_symbol}")
            self.update_token_balance()
        except Exception as e:
            self.processing_queue.put(f"Invalid contract address. Error: {e}. Please try again.")
            
    
    def update_token_balance(self):
        if self.token_contract and self.MY_ADDRESS:
            try:
                token_balance = self.token_contract.functions.balanceOf(self.MY_ADDRESS).call()
                token_decimals = self.token_contract.functions.decimals().call()
                token_symbol = self.token_contract.functions.symbol().call()
                token_balance_formatted = token_balance / 10**token_decimals
                self.token_info_label.configure(
                    text=f"Token Balance: {token_balance_formatted} {token_symbol}"
                )
            except Exception as e:
               self.processing_queue.put(f"Failed to fetch token balance: {str(e)}")


    def send_native_currency(self, recipient_address, amount, nonce, silent=False):
        try:
            recipient_address = self.web3.to_checksum_address(recipient_address)
            value_in_wei = self.web3.to_wei(amount, 'ether')
            eth_balance = self.web3.eth.get_balance(self.MY_ADDRESS)

            gas_price = self.web3.to_wei('1', 'gwei')
            gas_limit = 21000
            transaction_cost = gas_price * gas_limit
            
            if eth_balance < (transaction_cost + value_in_wei):
                self.processing_queue.put(f"Insufficient ETH balance for the transaction! Address: {recipient_address}")
                return False, "Insufficient ETH balance"

            txn = {
                'to': recipient_address,
                'value': value_in_wei,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.CHAIN_ID
            }
            
            signed_txn = self.web3.eth.account.sign_transaction(txn, self.PRIVATE_KEY)
            txn_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            if not silent:
                self.processing_queue.put(f"Transaction sent with hash: {self.web3.to_hex(txn_hash)}")
                self.processing_queue.put("Waiting for transaction confirmation...")
            
            receipt = self.web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)
            
            if not silent:
                if receipt['status'] == 1:
                    self.processing_queue.put("Transaction successful! 🟢")
                    self.processing_queue.put(f"Transaction explorer URL: {self.EXPLORER_URL}/tx/{self.web3.to_hex(txn_hash)}")
                else:
                    self.processing_queue.put("Transaction failed! 🔴")
                    self.processing_queue.put(f"Check transaction: {self.EXPLORER_URL}/tx/{self.web3.to_hex(txn_hash)}")
            
            return txn_hash, None

        except Exception as e:
            self.processing_queue.put(f"An error occurred while sending native currency: {str(e)}")
            return None, str(e)

    def send_tokens(self, recipient_address, amount, nonce, silent=False):
        try:
            recipient_address = self.web3.to_checksum_address(recipient_address)
            token_decimals = self.token_contract.functions.decimals().call()
            
            value_in_wei = int(Decimal(amount) * Decimal(10 ** token_decimals))
            token_balance = self.token_contract.functions.balanceOf(self.MY_ADDRESS).call()
            
            if token_balance < value_in_wei:
                self.processing_queue.put(f"Insufficient token balance for the transaction! Address: {recipient_address}")
                return False, "Insufficient token balance"
            
            gas_price = self.web3.to_wei('1', 'gwei')
            gas_limit = 60000
            
            eth_balance = self.web3.eth.get_balance(self.MY_ADDRESS)
            
            if eth_balance < (gas_price * gas_limit):
                self.processing_queue.put(f"Insufficient ETH balance for gas fees! Address: {recipient_address}")
                return None, "Insufficient ETH for gas fees"
            
            txn = self.token_contract.functions.transfer(recipient_address, value_in_wei).build_transaction({
                'chainId': self.CHAIN_ID,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            
            signed_txn = self.web3.eth.account.sign_transaction(txn, self.PRIVATE_KEY)
            txn_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            if not silent:
               self.processing_queue.put(f"Transaction sent with hash: {self.web3.to_hex(txn_hash)}")
               self.processing_queue.put("Waiting for transaction confirmation...")
            
            receipt = self.web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)
            
            if not silent:
                if receipt['status'] == 1:
                    self.processing_queue.put("Transaction successful! 🟢")
                    self.processing_queue.put(f"Transaction explorer URL: {self.EXPLORER_URL}/tx/{self.web3.to_hex(txn_hash)}")
                else:
                   self.processing_queue.put("Transaction failed! 🔴")
                   self.processing_queue.put(f"Check transaction: {self.EXPLORER_URL}/tx/{self.web3.to_hex(txn_hash)}")
            
            return txn_hash, None

        except Exception as e:
            self.processing_queue.put(f"An error occurred while sending tokens: {str(e)}")
            return None, str(e)

    def process_multi_transfer(self, transfer_function, file_path):
         self.progress_frame.pack(fill="x", pady=5)
         self.progress_bar.set(0)
         self.progress_label.configure(text="Preparing...")
         threading.Thread(target=self._process_multi_transfer_thread, args=(transfer_function, file_path), daemon=True).start()

    def _process_multi_transfer_thread(self, transfer_function, file_path):
        successful_transactions_count = 0
        failed_transactions_count = 0
        current_nonce = self.web3.eth.get_transaction_count(self.MY_ADDRESS)
        nonce_lock = threading.Lock()
        transactions = []
        
        def send_transaction(index, recipient, amount, nonce):
            nonlocal successful_transactions_count, failed_transactions_count

            try:
                if transfer_function == self.send_tokens:
                    txn_hash, error = transfer_function(recipient, amount, nonce, silent=True)
                else:
                    txn_hash, error = transfer_function(recipient, amount, nonce, silent=True)
                
                if txn_hash:
                    # Wait for transaction receipt
                    receipt = self.web3.eth.wait_for_transaction_receipt(txn_hash, timeout=300)
                    success = receipt['status'] == 1
                    
                    if success:
                       successful_transactions_count += 1
                    else:
                        failed_transactions_count += 1
                    
                    transactions.append({
                        'index': index + 1,
                        'recipient': recipient,
                        'amount': amount,
                        'status': 'Success' if success else 'Failed',
                        'hash': self.web3.to_hex(txn_hash),
                        'explorer_url': f"{self.EXPLORER_URL}/tx/{self.web3.to_hex(txn_hash)}"
                    })
                else:
                     failed_transactions_count += 1
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
                failed_transactions_count += 1
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
            self.processing_queue.put("Preparing multi-transfer...")
            data = pd.read_excel(file_path)
            if "Amount" not in data.columns or "Receiver" not in data.columns:
               self.processing_queue.put("Excel file must have 'Amount' and 'Receiver' columns.")
               self.after(0, self.progress_frame.pack_forget)
               return

            total_amount = sum(data['Amount'])
            
            if transfer_function == self.send_tokens and self.token_contract:
                token_symbol = self.token_contract.functions.symbol().call()
                confirm_msg = f"Total amount to be transferred: {total_amount} {token_symbol}"
            else:
                confirm_msg = f"Total amount to be transferred: {total_amount} ETH"
            
            if not messagebox.askyesno("Confirm Transfer", f"{confirm_msg}\nDo you want to proceed?"):
                self.processing_queue.put("Multi-transfer cancelled by user.")
                self.after(0, self.progress_frame.pack_forget)
                return
            
           
            total_transactions = len(data)
            self.processing_queue.put("Starting Transfers")
            
            for index, row in data.iterrows():
                recipient = row['Receiver']
                amount = row['Amount']
                progress = (index + 1) / total_transactions
                self.after(0, lambda: self.progress_bar.set(progress))
                self.after(0, lambda: self.progress_label.configure(
                    text=f"Processing transaction {index + 1}/{total_transactions}"))

                with nonce_lock:
                    send_transaction(index,recipient,amount,current_nonce)
                    current_nonce+=1

            
            self.after(0, self.progress_frame.pack_forget)
            self.processing_queue.put("\nTransfer Summary:")
            self.processing_queue.put(f"Total Transactions: {len(data)}")
            self.processing_queue.put(f"Successful: {successful_transactions_count}")
            self.processing_queue.put(f"Failed: {failed_transactions_count}")

            if messagebox.askyesno("Export Results", "Would you like to export the transaction summary?"):
                 self.after(0, lambda: self.export_results(transactions))
    
        except Exception as e:
            self.after(0, self.progress_frame.pack_forget)
            self.processing_queue.put(f"Multi-transfer error: {str(e)}")

    def export_results(self, transactions):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                initialfile=f"transaction_summary_{timestamp}.xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("Excel files", "*.xls")]
            )
            
            if filename:
                export_data = []
                failed_export_data = []
                for tx in transactions:
                    if tx['hash'] != 'N/A':
                        explorer_link = f'=HYPERLINK("{tx["explorer_url"]}", "{tx["hash"]}")'
                    else:
                        explorer_link = 'N/A'
                    
                    if tx["status"] == "Success":
                        export_data.append({
                            'Amount': tx['amount'],
                            'Receiver': tx['recipient'],
                            'Status': tx['status'],
                            'Hash': tx['hash'],
                            'View on Explorer': explorer_link,
                            'Error': tx.get('error', '')
                        })
                    elif tx["status"] == "Failed":
                         failed_export_data.append({
                            'Amount': tx['amount'],
                            'Receiver': tx['recipient'],
                            'Status': tx['status'],
                            'Hash': tx['hash'],
                            'View on Explorer': explorer_link,
                            'Error': tx.get('error', '')
                         })
                # Create DataFrame and export for all
                if export_data:
                    df = pd.DataFrame(export_data)
                    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
                    df.to_excel(writer, index=False, sheet_name='All Transactions')
                    writer.close()

                    self.processing_queue.put(f"Summary of successful transactions exported to: {filename}")

                if failed_export_data:
                   failed_filename = filename.replace(".xlsx", f"_failed_{timestamp}.xlsx")
                   df_failed = pd.DataFrame(failed_export_data)
                   writer_failed = pd.ExcelWriter(failed_filename, engine='xlsxwriter')
                   df_failed.to_excel(writer_failed, index=False, sheet_name='Failed Transactions')
                   writer_failed.close()
                   self.processing_queue.put(f"Summary of failed transactions exported to: {failed_filename}")
                if not export_data and not failed_export_data:
                    self.processing_queue.put("No transactions to export")
        
        except Exception as e:
            self.processing_queue.put(f"Failed to export results: {str(e)}")

    def update_native_balance(self):
        if self.web3 and self.MY_ADDRESS:
            try:
                balance = self.web3.eth.get_balance(self.MY_ADDRESS)
                eth_balance = self.web3.from_wei(balance, 'ether')
                self.native_balance_label.configure(
                    text=f"Current Balance: {eth_balance} ETH"
                )
            except Exception as e:
                 self.processing_queue.put(f"Failed to fetch balance: {str(e)}")

    def native_single_transfer(self):
        try:
            amount = float(self.native_amount_entry.get())
            recipient = self.native_recipient_entry.get().strip()
            
            if messagebox.askyesno("Confirm Transfer", 
                                 f"Send {amount} ETH to {recipient}?"):
                
                current_nonce = self.web3.eth.get_transaction_count(self.MY_ADDRESS)
                self.send_native_currency(recipient, amount, current_nonce)
                self.update_native_balance()
                
        except ValueError:
            self.processing_queue.put("Please enter a valid amount")
        except Exception as e:
             self.processing_queue.put(f"Error during single transfer: {str(e)}")

    def token_single_transfer(self):
        try:
            if not self.token_contract:
                self.processing_queue.put("Please initialize contract first")
                return
                
            amount = float(self.token_amount_entry.get())
            recipient = self.token_recipient_entry.get().strip()
            
            token_symbol = self.token_contract.functions.symbol().call()
            
            if messagebox.askyesno("Confirm Transfer", 
                                 f"Send {amount} {token_symbol} to {recipient}?"):
                
                current_nonce = self.web3.eth.get_transaction_count(self.MY_ADDRESS)
                self.send_tokens(recipient, amount, current_nonce)
                self.update_token_balance()
                
        except ValueError:
            self.processing_queue.put("Please enter a valid amount")
        except Exception as e:
             self.processing_queue.put(f"Error during single token transfer: {str(e)}")

    def native_multi_transfer(self):
       file_path = filedialog.askopenfilename(
           filetypes=[("Excel files", "*.xlsx"), ("Excel files", "*.xls")]
        )
       if file_path:
            try:
               self.process_multi_transfer(self.send_native_currency, file_path)
               self.update_native_balance()
            except Exception as e:
                 self.processing_queue.put(f"Error during multi native transfer: {str(e)}")

    def token_multi_transfer(self):
        if not self.token_contract:
            self.processing_queue.put("Please initialize contract first")
            return
            
        file_path = filedialog.askopenfilename(
             filetypes=[("Excel files", "*.xlsx"), ("Excel files", "*.xls")]
        )
        if file_path:
            try:
                self.process_multi_transfer(self.send_tokens, file_path)
                self.update_token_balance()
            except Exception as e:
                 self.processing_queue.put(f"Error during multi token transfer: {str(e)}")
                
if __name__ == "__main__":
    app = TokenTransferApp()
    app.mainloop()
