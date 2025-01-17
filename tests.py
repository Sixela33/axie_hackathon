from os import environ
from web3 import Web3
from web3.middleware import geth_poa_middleware
import time
import sys
import logging
from database import engine, SessionLocal
import models

models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Get env variables or set to default
startBlock = "1"
confirmationBlocks = environ.get("CONFIRMATIONS_BLOCK") or "0"
nodeUrl = "https://ronin-mainnet.core.chainstack.com/8822ab2f40395d7919bc9c00f7183882"
pollingPeriod = "20"
logFile = 'logs.log'

# Connect to Ethereum node
if nodeUrl.startswith("http"):
    web3 = Web3(Web3.HTTPProvider(nodeUrl)) # "http://publicnode:8545"
elif nodeUrl.startswith("ws"):
    web3 = Web3(Web3.WebsocketProvider(nodeUrl)) # "ws://publicnode:8546"
else:
    web3 = Web3(Web3.IPCProvider(nodeUrl)) # "/home/geth/.ethereum/geth.ipc"

web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Start logger
#logger = logging.getLogger("EthIndexerLog")
logger = logging.getLogger("eth-sync")
logger.setLevel(logging.INFO)

# File logger
if logFile == None:
    lfh = logging.StreamHandler()
else:
    lfh = logging.FileHandler(logFile)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
lfh.setFormatter(formatter)
logger.addHandler(lfh)

# Systemd logger, if we want to user journalctl logs
# Install systemd-python and
# decomment "#from systemd.journal import JournalHandler" up
#ljc = JournalHandler()
#formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#ljc.setFormatter(formatter)
#logger.addHandler(ljc)

try:
    logger.info("Trying to connect to " + dbname + " database…")
    conn = psycopg2.connect(database=dbname)
    conn.autocommit = True
    logger.info("Connected to the database")
except:
    logger.error("Unable to connect to database")
    exit(1)

# Delete last block as it may be not imported in full
cur = conn.cursor()
cur.execute('DELETE FROM public.ethtxs WHERE block = (SELECT Max(block) from public.ethtxs)')
cur.close()
conn.close()

# Wait for the node to be in sync before indexing
while web3.eth.syncing != False:
    # Change with the time, in second, do you want to wait
    # before checking again, default is 5 minutes
    logger.info("Waiting Ethereum node to be in sync…")
    time.sleep(300)

logger.info("Ethereum node is synced.")

# Adds all transactions from Ethereum block
def insertTxsFromBlock(block):
    blockid = block['number']
    time = block['timestamp']
    for txNumber in range(0, len(block.transactions)):
        trans = block.transactions[txNumber]
        transReceipt = web3.eth.get_transaction_receipt(trans['hash'])
        # Save also transaction status, should be null if pre byzantium blocks
        # status = bool(transReceipt['status'])
        txhash = trans['hash'].hex()
        value = trans['value']
        inputinfo = trans['input']
        # Check if transaction is a contract transfer
        if (value == 0 and not inputinfo.hex().startswith('0xa9059cbb')):
            continue
        fr = trans['from']
        to = trans['to']
        gasprice = trans['gasPrice']
        gas = transReceipt['gasUsed']
        contract_to = ''
        contract_value = ''
        # Check if transaction is a contract transfer
        if inputinfo.hex().startswith('0xa9059cbb'):
            contract_to = inputinfo.hex()[10:-64]
            contract_value = inputinfo.hex()[74:]
        # Correct contract transfer transaction represents '0x' + 4 bytes 'a9059cbb' + 32 bytes (64 chars) for contract address and 32 bytes for its value
        # Some buggy txs can break up Indexer, so we'll filter it
        if len(contract_to) > 128:
            logger.info('Skipping ' + str(txhash) + ' tx. Incorrect contract_to length: ' + str(len(contract_to)))
            contract_to = ''
            contract_value = ''
        cur.execute(
            'INSERT INTO public.ethtxs(time, txfrom, txto, value, gas, gasprice, block, txhash, contract_to, contract_value) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (time, fr, to, value, gas, gasprice, blockid, txhash, contract_to, contract_value))

# Fetch all of new (not in index) Ethereum blocks and add transactions to index
while True:
    try:
        conn = psycopg2.connect(database=dbname)
        conn.autocommit = True
    except:
        logger.error("Unable to connect to database")

    cur = conn.cursor()

    cur.execute('SELECT Max(block) from public.ethtxs')
    maxblockindb = cur.fetchone()[0]
    # On first start, we index transactions from a block number you indicate
    if maxblockindb is None:
        maxblockindb = int(startBlock)

    endblock = int(web3.eth.block_number) - int(confirmationBlocks)

    logger.info('Current best block in index: ' + str(maxblockindb) + '; in Ethereum chain: ' + str(endblock))

    for blockHeight in range(maxblockindb + 1, endblock):
        block = web3.eth.get_block(blockHeight, True)
        if len(block.transactions) > 0:
            insertTxsFromBlock(block)
            logger.info('Block ' + str(blockHeight) + ' with ' + str(len(block.transactions)) + ' transactions is processed')
        else:
            logger.info('Block ' + str(blockHeight) + ' does not contain transactions')
    cur.close()
    conn.close()
    time.sleep(int(pollingPeriod))
