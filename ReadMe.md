Send Tokens to multiple accounts with your personal computer

## V1 and V2

V1 is a basic tool which does transactions one address at a time ,  so initalize a transaction <-> wait for confirmation <-> initalize the next transaction . If a transaction is failed , then the script is stopped by default and would need a human interference to start again.

V2 is a advanced tool made on top of V1 with functions like multithreading , so that all the transactions are initalized nearly at the same time but are not needed to wait for confirmation of the previous initialized transaction to be confirmed. This gives a summary at the end with failed and success logs for each transaction . The disadvantage of this method is , if you have set a low gas price then all the transactions will fail and you will end up loosing the gas amount. 

## Adjusting Gas Fees

To change the gas fees for transactions, please modify the following parameters in the [code](https://github.com/parzivalishan/newsuper/blob/main/tools/MultiSender.py) on the line 55-58 , you would need to change the 0.51 and 40000 according to your needs and network conditions:

```python
# Estimate the gas for the transaction
gas_price = web3.to_wei('0.51', 'gwei')  # Gas price in gwei
gas_limit = 40000  # Gas limit
transaction_cost = gas_price * gas_limit

```

## XLSX File Format (Required only For using Multisend Functionality )
Make an Excel file with two colums named as Amount and Receiver like the following and add the data in it to use the multisend functionality of the tool




| Amount | Receiver |
|--------|----------|
| 100    | 0x220866B1A2219f40e72f5c628B65D54268cA3A9D|
| 200    | 0x86A41524CB61edd8B115A72Ad9735F8068996688 |
| 150    | 0x86A41524CB61edd8B115A72Ad9735F8068996688  |
