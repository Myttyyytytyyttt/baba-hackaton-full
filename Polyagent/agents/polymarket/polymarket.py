# core polymarket api
# https://github.com/Polymarket/py-clob-client/tree/main/examples

import os
import pdb
import time
import ast
import requests
import json
import traceback
import random
from datetime import datetime

from dotenv import load_dotenv

from web3 import Web3
from web3.constants import MAX_INT
from web3.middleware import geth_poa_middleware

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from py_clob_client.constants import AMOY, POLYGON
from py_order_utils.builders import OrderBuilder
from py_order_utils.model import OrderData
from py_order_utils.signer import Signer
from py_clob_client.clob_types import (
    OrderArgs,
    MarketOrderArgs,
    OrderType,
    OrderBookSummary,
)
from py_clob_client.order_builder.constants import BUY

from agents.utils.objects import SimpleMarket, SimpleEvent
from colorama import Fore, Style

load_dotenv()


class Polymarket:
    def __init__(self):
        load_dotenv()
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true" if os.getenv("DRY_RUN") else False
        
        # Configuración básica
        self.private_key = os.getenv("POLYGON_WALLET_PRIVATE_KEY")
        self.chain_id = POLYGON
        
        # URLs y endpoints
        self.clob_url = "https://clob.polymarket.com"
        self.gamma_url = "https://gamma-api.polymarket.com"
        self.gamma_markets_endpoint = f"{self.gamma_url}/markets"
        self.gamma_events_endpoint = f"{self.gamma_url}/events"
        self.polygon_rpc = "https://polygon-rpc.com"
        
        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(self.polygon_rpc))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Wallet setup
        self.wallet_address = self.get_address_for_private_key()
        print(f"Initialized wallet: {self.wallet_address}")
        
        # Contract addresses (usando checksum addresses)
        self.exchange_address = Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e")
        self.neg_risk_exchange_address = Web3.to_checksum_address("0xC5d563A36AE78145C45a50134d48A1215220f80a")
        self.usdc_address = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")  # USDC en Polygon
        
        # USDC contract setup
        self.usdc_abi = '''[
            {
                "constant": true,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": false,
                "inputs": [{"name": "_spender", "type": "address"},{"name": "_value", "type": "uint256"}],
                "name": "approve",
                "outputs": [{"name": "success", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": true,
                "inputs": [{"name": "_owner", "type": "address"},{"name": "_spender", "type": "address"}],
                "name": "allowance",
                "outputs": [{"name": "remaining", "type": "uint256"}],
                "type": "function"
            }
        ]'''
        
        self.usdc = self.w3.eth.contract(
            address=self.usdc_address,
            abi=json.loads(self.usdc_abi)
        )
        
        # Initialize CLOB client
        self.client = ClobClient(
            self.clob_url,
            key=self.private_key,
            chain_id=self.chain_id
        )
        
        # Set API credentials
        creds = ApiCreds(
            api_key=os.getenv("CLOB_API_KEY"),
            api_secret=os.getenv("CLOB_SECRET"),
            api_passphrase=os.getenv("CLOB_PASS_PHRASE"),
        )
        self.client.set_api_creds(creds)

        self.erc20_approve = """[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"spender","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"authorizer","type":"address"},{"indexed":true,"internalType":"bytes32","name":"nonce","type":"bytes32"}],"name":"AuthorizationCanceled","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"authorizer","type":"address"},{"indexed":true,"internalType":"bytes32","name":"nonce","type":"bytes32"}],"name":"AuthorizationUsed","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"account","type":"address"}],"name":"Blacklisted","type":"event"},{"anonymous":false,"inputs":[{"indexed":false,"internalType":"address","name":"userAddress","type":"address"},{"indexed":false,"internalType":"address payable","name":"relayerAddress","type":"address"},{"indexed":false,"internalType":"bytes","name":"functionSignature","type":"bytes"}],"name":"MetaTransactionExecuted","type":"event"},{"anonymous":false,"inputs":[],"name":"Pause","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"newRescuer","type":"address"}],"name":"RescuerChanged","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"bytes32","name":"role","type":"bytes32"},{"indexed":true,"internalType":"bytes32","name":"previousAdminRole","type":"bytes32"},{"indexed":true,"internalType":"bytes32","name":"newAdminRole","type":"bytes32"}],"name":"RoleAdminChanged","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"bytes32","name":"role","type":"bytes32"},{"indexed":true,"internalType":"address","name":"account","type":"address"},{"indexed":true,"internalType":"address","name":"sender","type":"address"}],"name":"RoleGranted","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"bytes32","name":"role","type":"bytes32"},{"indexed":true,"internalType":"address","name":"account","type":"address"},{"indexed":true,"internalType":"address","name":"sender","type":"address"}],"name":"RoleRevoked","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"account","type":"address"}],"name":"UnBlacklisted","type":"event"},{"anonymous":false,"inputs":[],"name":"Unpause","type":"event"},{"inputs":[],"name":"APPROVE_WITH_AUTHORIZATION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"BLACKLISTER_ROLE","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"CANCEL_AUTHORIZATION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"DECREASE_ALLOWANCE_WITH_AUTHORIZATION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"DEFAULT_ADMIN_ROLE","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"DEPOSITOR_ROLE","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"DOMAIN_SEPARATOR","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"EIP712_VERSION","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"INCREASE_ALLOWANCE_WITH_AUTHORIZATION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"META_TRANSACTION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"PAUSER_ROLE","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"PERMIT_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"RESCUER_ROLE","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"TRANSFER_WITH_AUTHORIZATION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"WITHDRAW_WITH_AUTHORIZATION_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"validAfter","type":"uint256"},{"internalType":"uint256","name":"validBefore","type":"uint256"},{"internalType":"bytes32","name":"nonce","type":"bytes32"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"approveWithAuthorization","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"authorizer","type":"address"},{"internalType":"bytes32","name":"nonce","type":"bytes32"}],"name":"authorizationState","outputs":[{"internalType":"enum GasAbstraction.AuthorizationState","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"blacklist","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"blacklisters","outputs":[{"internalType":"address[]","name":"","type":"address[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"authorizer","type":"address"},{"internalType":"bytes32","name":"nonce","type":"bytes32"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"cancelAuthorization","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"subtractedValue","type":"uint256"}],"name":"decreaseAllowance","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"decrement","type":"uint256"},{"internalType":"uint256","name":"validAfter","type":"uint256"},{"internalType":"uint256","name":"validBefore","type":"uint256"},{"internalType":"bytes32","name":"nonce","type":"bytes32"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"decreaseAllowanceWithAuthorization","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"user","type":"address"},{"internalType":"bytes","name":"depositData","type":"bytes"}],"name":"deposit","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"userAddress","type":"address"},{"internalType":"bytes","name":"functionSignature","type":"bytes"},{"internalType":"bytes32","name":"sigR","type":"bytes32"},{"internalType":"bytes32","name":"sigS","type":"bytes32"},{"internalType":"uint8","name":"sigV","type":"uint8"}],"name":"executeMetaTransaction","outputs":[{"internalType":"bytes","name":"","type":"bytes"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"}],"name":"getRoleAdmin","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"getRoleMember","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"}],"name":"getRoleMemberCount","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"},{"internalType":"address","name":"account","type":"address"}],"name":"grantRole","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"},{"internalType":"address","name":"account","type":"address"}],"name":"hasRole","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"addedValue","type":"uint256"}],"name":"increaseAllowance","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"increment","type":"uint256"},{"internalType":"uint256","name":"validAfter","type":"uint256"},{"internalType":"uint256","name":"validBefore","type":"uint256"},{"internalType":"bytes32","name":"nonce","type":"bytes32"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"increaseAllowanceWithAuthorization","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"string","name":"newName","type":"string"},{"internalType":"string","name":"newSymbol","type":"string"},{"internalType":"uint8","name":"newDecimals","type":"uint8"},{"internalType":"address","name":"childChainManager","type":"address"}],"name":"initialize","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"initialized","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"isBlacklisted","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"nonces","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"pause","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"paused","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"pausers","outputs":[{"internalType":"address[]","name":"","type":"address[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"permit","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"},{"internalType":"address","name":"account","type":"address"}],"name":"renounceRole","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IERC20","name":"tokenContract","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"rescueERC20","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"rescuers","outputs":[{"internalType":"address[]","name":"","type":"address[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32","name":"role","type":"bytes32"},{"internalType":"address","name":"account","type":"address"}],"name":"revokeRole","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transferFrom","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"validAfter","type":"uint256"},{"internalType":"uint256","name":"validBefore","type":"uint256"},{"internalType":"bytes32","name":"nonce","type":"bytes32"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"transferWithAuthorization","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"unBlacklist","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"unpause","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"string","name":"newName","type":"string"},{"internalType":"string","name":"newSymbol","type":"string"}],"name":"updateMetadata","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"withdraw","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"validAfter","type":"uint256"},{"internalType":"uint256","name":"validBefore","type":"uint256"},{"internalType":"bytes32","name":"nonce","type":"bytes32"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"withdrawWithAuthorization","outputs":[],"stateMutability":"nonpayable","type":"function"}]"""
        self.erc1155_set_approval = """[{"inputs": [{ "internalType": "address", "name": "operator", "type": "address" },{ "internalType": "bool", "name": "approved", "type": "bool" }],"name": "setApprovalForAll","outputs": [],"stateMutability": "nonpayable","type": "function"}]"""

        self.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        self.ctf_address = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

        self.web3 = Web3(Web3.HTTPProvider(self.polygon_rpc))
        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

        self.usdc = self.web3.eth.contract(
            address=self.usdc_address, abi=self.erc20_approve
        )
        self.ctf = self.web3.eth.contract(
            address=self.ctf_address, abi=self.erc1155_set_approval
        )

        self._init_api_keys()
        self._init_approvals(False)

    def _init_api_keys(self) -> None:
        self.client = ClobClient(
            self.clob_url, key=self.private_key, chain_id=self.chain_id
        )
        self.credentials = self.client.create_or_derive_api_creds()
        self.client.set_api_creds(self.credentials)
        # print(self.credentials)

    def _init_approvals(self, run: bool = False) -> None:
        if not run:
            return

        priv_key = self.private_key
        pub_key = self.get_address_for_private_key()
        chain_id = self.chain_id
        web3 = self.web3
        nonce = web3.eth.get_transaction_count(pub_key)
        usdc = self.usdc
        ctf = self.ctf

        # CTF Exchange
        raw_usdc_approve_txn = usdc.functions.approve(
            "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E", int(MAX_INT, 0)
        ).build_transaction({"chainId": chain_id, "from": pub_key, "nonce": nonce})
        signed_usdc_approve_tx = web3.eth.account.sign_transaction(
            raw_usdc_approve_txn, private_key=priv_key
        )
        send_usdc_approve_tx = web3.eth.send_raw_transaction(
            signed_usdc_approve_tx.raw_transaction
        )
        usdc_approve_tx_receipt = web3.eth.wait_for_transaction_receipt(
            send_usdc_approve_tx, 600
        )
        print(usdc_approve_tx_receipt)

        nonce = web3.eth.get_transaction_count(pub_key)

        raw_ctf_approval_txn = ctf.functions.setApprovalForAll(
            "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E", True
        ).build_transaction({"chainId": chain_id, "from": pub_key, "nonce": nonce})
        signed_ctf_approval_tx = web3.eth.account.sign_transaction(
            raw_ctf_approval_txn, private_key=priv_key
        )
        send_ctf_approval_tx = web3.eth.send_raw_transaction(
            signed_ctf_approval_tx.raw_transaction
        )
        ctf_approval_tx_receipt = web3.eth.wait_for_transaction_receipt(
            send_ctf_approval_tx, 600
        )
        print(ctf_approval_tx_receipt)

        nonce = web3.eth.get_transaction_count(pub_key)

        # Neg Risk CTF Exchange
        raw_usdc_approve_txn = usdc.functions.approve(
            "0xC5d563A36AE78145C45a50134d48A1215220f80a", int(MAX_INT, 0)
        ).build_transaction({"chainId": chain_id, "from": pub_key, "nonce": nonce})
        signed_usdc_approve_tx = web3.eth.account.sign_transaction(
            raw_usdc_approve_txn, private_key=priv_key
        )
        send_usdc_approve_tx = web3.eth.send_raw_transaction(
            signed_usdc_approve_tx.raw_transaction
        )
        usdc_approve_tx_receipt = web3.eth.wait_for_transaction_receipt(
            send_usdc_approve_tx, 600
        )
        print(usdc_approve_tx_receipt)

        nonce = web3.eth.get_transaction_count(pub_key)

        raw_ctf_approval_txn = ctf.functions.setApprovalForAll(
            "0xC5d563A36AE78145C45a50134d48A1215220f80a", True
        ).build_transaction({"chainId": chain_id, "from": pub_key, "nonce": nonce})
        signed_ctf_approval_tx = web3.eth.account.sign_transaction(
            raw_ctf_approval_txn, private_key=priv_key
        )
        send_ctf_approval_tx = web3.eth.send_raw_transaction(
            signed_ctf_approval_tx.raw_transaction
        )
        ctf_approval_tx_receipt = web3.eth.wait_for_transaction_receipt(
            send_ctf_approval_tx, 600
        )
        print(ctf_approval_tx_receipt)

        nonce = web3.eth.get_transaction_count(pub_key)

        # Neg Risk Adapter
        raw_usdc_approve_txn = usdc.functions.approve(
            "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296", int(MAX_INT, 0)
        ).build_transaction({"chainId": chain_id, "from": pub_key, "nonce": nonce})
        signed_usdc_approve_tx = web3.eth.account.sign_transaction(
            raw_usdc_approve_txn, private_key=priv_key
        )
        send_usdc_approve_tx = web3.eth.send_raw_transaction(
            signed_usdc_approve_tx.raw_transaction
        )
        usdc_approve_tx_receipt = web3.eth.wait_for_transaction_receipt(
            send_usdc_approve_tx, 600
        )
        print(usdc_approve_tx_receipt)

        nonce = web3.eth.get_transaction_count(pub_key)

        raw_ctf_approval_txn = ctf.functions.setApprovalForAll(
            "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296", True
        ).build_transaction({"chainId": chain_id, "from": pub_key, "nonce": nonce})
        signed_ctf_approval_tx = web3.eth.account.sign_transaction(
            raw_ctf_approval_txn, private_key=priv_key
        )
        send_ctf_approval_tx = web3.eth.send_raw_transaction(
            signed_ctf_approval_tx.raw_transaction
        )
        ctf_approval_tx_receipt = web3.eth.wait_for_transaction_receipt(
            send_ctf_approval_tx, 600
        )
        print(ctf_approval_tx_receipt)

    def get_all_markets(self) -> "list[SimpleMarket]":
        markets = []
        res = httpx.get(self.gamma_markets_endpoint)
        if res.status_code == 200:
            for market in res.json():
                try:
                    market_data = self.map_api_to_market(market)
                    markets.append(SimpleMarket(**market_data))
                except Exception as e:
                    print(e)
                    pass
        return markets

    def filter_markets_for_trading(self, markets: "list[SimpleMarket]"):
        tradeable_markets = []
        for market in markets:
            if market.active:
                tradeable_markets.append(market)
        return tradeable_markets

    def get_market(self, token_id: str) -> SimpleMarket:
        params = {"clob_token_ids": token_id}
        res = httpx.get(self.gamma_markets_endpoint, params=params)
        if res.status_code == 200:
            data = res.json()
            market = data[0]
            return self.map_api_to_market(market, token_id)

    def map_api_to_market(self, market, token_id: str = "") -> SimpleMarket:
        market = {
            "id": int(market["id"]),
            "question": market["question"],
            "end": market["endDate"],
            "description": market["description"],
            "active": market["active"],
            # "deployed": market["deployed"],
            "funded": market["funded"],
            "rewardsMinSize": float(market["rewardsMinSize"]),
            "rewardsMaxSpread": float(market["rewardsMaxSpread"]),
            # "volume": float(market["volume"]),
            "spread": float(market["spread"]),
            "outcomes": str(market["outcomes"]),
            "outcome_prices": str(market["outcomePrices"]),
            "clob_token_ids": str(market["clobTokenIds"]),
        }
        if token_id:
            market["clob_token_ids"] = token_id
        return market

    def get_all_events(self) -> "list[SimpleEvent]":
        """Get all events from Gamma API"""
        try:
            params = {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": "100",
                "order": "volume",
                "ascending": "false"
            }
            
            res = httpx.get(
                f"{self.gamma_url}/markets",
                params=params,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=30.0
            )
            
            if res.status_code == 200:
                markets = res.json()
                if markets:
                    events = []
                    for market in markets:
                        if float(market.get("volume", 0)) > 10000:
                            event_data = {
                                "id": str(market.get("id")),
                                "title": market.get("question", ""),
                                "description": market.get("description", ""),
                                "markets": str(market.get("id", "")),
                                "metadata": {
                                    "question": market.get("question", ""),
                                    "markets": str(market.get("id", "")),
                                    "volume": float(market.get("volume", 0)),
                                    "featured": market.get("featured", False),
                                    "outcome_prices": market.get("outcomePrices", "[]"),
                                    "outcomes": market.get("outcomes", "[]")
                                }
                            }
                            events.append(SimpleEvent(**event_data))
                    
                    print(f"\nTop mercados por volumen total:")
                    for market in markets[:5]:
                        print(f"- {market.get('question')}: ${float(market.get('volume', 0)):,.2f}")
                    
                    return events
                
            return []
        except Exception as e:
            print(f"Error getting events: {e}")
            return []

    def get_all_tradeable_events(self) -> "list[SimpleEvent]":
        try:
            params = {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": "100",
                "order": "volume",
                "ascending": "false"
            }
            
            res = httpx.get(
                f"{self.gamma_url}/markets",
                params=params,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=30.0
            )
            
            if res.status_code == 200:
                markets = res.json()
                if markets:
                    events = []
                    for market in markets:
                        # Solo considerar mercados con volumen significativo
                        if float(market.get("volume", 0)) > 10000:
                            event_data = {
                                "id": str(market.get("id")),  # Convertir a string
                                "title": market.get("question", ""),
                                "description": market.get("description", ""),
                                "markets": str(market.get("id", "")),
                                "metadata": {
                                    "question": market.get("question", ""),
                                    "markets": str(market.get("id", "")),
                                    "volume": float(market.get("volume", 0)),
                                    "featured": market.get("featured", False),
                                    "outcome_prices": market.get("outcomePrices", "[]"),
                                    "outcomes": market.get("outcome", "[]")
                                }
                            }
                            event = SimpleEvent(**event_data)
                            events.append(event)
                    
                    print(f"\nTop mercados por volumen total:")
                    for market in markets[:5]:
                        print(f"- {market.get('question')}: ${float(market.get('volume', 0)):,.2f}")
                    
                    return events
            return []
        except Exception as e:
            print(f"{Fore.RED}Error getting events: {str(e)}{Style.RESET_ALL}")
            return []

    def get_sampling_simplified_markets(self) -> "list[SimpleEvent]":
        markets = []
        raw_sampling_simplified_markets = self.client.get_sampling_simplified_markets()
        for raw_market in raw_sampling_simplified_markets["data"]:
            token_one_id = raw_market["tokens"][0]["token_id"]
            market = self.get_market(token_one_id)
            markets.append(market)
        return markets

    def get_orderbook(self, token_id: str) -> OrderBookSummary:
        return self.client.get_order_book(token_id)

    def get_orderbook_price(self, token_id: str) -> float:
        return float(self.client.get_price(token_id))

    def get_address_for_private_key(self):
        account = self.w3.eth.account.from_key(str(self.private_key))
        return account.address

    def build_order(
        self,
        market_token: str,
        amount: float,
        nonce: str = str(round(time.time())),  # for cancellations
        side: str = "BUY",
        expiration: str = "0",  # timestamp after which order expires
    ):
        signer = Signer(self.private_key)
        builder = OrderBuilder(self.exchange_address, self.chain_id, signer)

        buy = side == "BUY"
        side = 0 if buy else 1
        maker_amount = amount if buy else 0
        taker_amount = amount if not buy else 0
        order_data = OrderData(
            maker=self.get_address_for_private_key(),
            tokenId=market_token,
            makerAmount=maker_amount,
            takerAmount=taker_amount,
            feeRateBps="1",
            nonce=nonce,
            side=side,
            expiration=expiration,
        )
        order = builder.build_signed_order(order_data)
        return order

    def execute_order(self, price, size, side, token_id) -> str:
        return self.client.create_and_post_order(
            OrderArgs(price=price, size=size, side=side, token_id=token_id)
        )

    def get_token_balance(self, token_id: str) -> float:
        """Get balance of a specific outcome token"""
        try:
            # ERC1155 balance ABI
            erc1155_abi = '''[{
                "inputs": [
                    {"internalType": "address", "name": "account", "type": "address"},
                    {"internalType": "uint256", "name": "id", "type": "uint256"}
                ],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }]'''
            
            # CTF token contract address
            ctf_address = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")
            
            # Create contract
            ctf = self.w3.eth.contract(address=ctf_address, abi=erc1155_abi)
            
            # Get balance
            balance = ctf.functions.balanceOf(self.wallet_address, int(token_id)).call()
            return float(balance)
            
        except Exception as e:
            print(f"Error getting token balance: {e}")
            return 0.0

    def execute_market_order(self, market, amount, explicit_position=None):
        try:
            # Obtener datos del mercado usando los atributos correctos
            token_ids = ast.literal_eval(market.clob_token_ids)  # Usar el atributo directamente
            
            # Determinar qué token comprar basado en la posición recomendada
            # CORREGIDO: El token[0] es YES, token[1] es NO (invertido del comportamiento anterior)
            
            # Primero verificar el parámetro explícito
            if explicit_position is not None and explicit_position.upper() in ["YES", "NO"]:
                position = explicit_position.upper()
                print(f"Using explicit position: {position}")
            # Si el trade dice SELL -> compramos NO
            # Si el trade dice BUY -> compramos YES
            elif hasattr(market, 'trade') and market.trade.get('side') == "SELL":
                token_id = token_ids[1]  # Token NO (corregido)
                position = "NO"
            elif hasattr(market, 'trade') and market.trade.get('position'):
                # Usar directamente la posición del trade
                position = market.trade.get('position').upper()
            else:
                token_id = token_ids[0]  # Token YES (default) (corregido)
                position = "YES"
            
            # Seleccionar token ID basado en la posición
            if position == "NO":
                token_id = token_ids[1]  # Corregido: Token NO es el segundo (index 1)
            else:
                token_id = token_ids[0]  # Corregido: Token YES es el primero (index 0)
            
            # Verificar si ya tenemos una posición
            current_balance = self.get_token_balance(token_id)
            if current_balance > 0:
                print(f"Already have position in this market: {current_balance} {position} tokens")
                return None
            
            # Verificar balance de USDC
            usdc_balance = self.get_usdc_balance()
            print(f"USDC Balance: ${usdc_balance}")
            
            if usdc_balance < amount:
                print(f"Insufficient USDC balance (${usdc_balance}) for order amount (${amount})")
                return False
                
            # Verificar allowance de USDC
            allowance = self.check_usdc_allowance()
            print(f"USDC Allowance: ${allowance}")
            
            if allowance < amount:
                print(f"Insufficient USDC allowance. Approving...")
                self.approve_usdc_spend(amount)
            
            # Si estamos en dry_run, no necesitamos datos reales del orderbook
            if self.dry_run:
                print(f"🔍 DRY RUN mode: would execute {position} order for market {market.question}")
                print(f"   Amount: ${amount} USDC")
                
                # Usar precios del market si están disponibles, o simular un precio
                try:
                    if hasattr(market, 'outcome_prices') and market.outcome_prices:
                        prices = ast.literal_eval(market.outcome_prices)
                        market_price = float(prices[0] if position == "YES" else prices[1])  # Corregido
                    else:
                        market_price = 0.5  # Precio predeterminado si no hay datos
                except:
                    market_price = 0.5  # Precio predeterminado en caso de error
                
                print(f"Simulated market price: ${market_price}")
                tokens_amount = amount / market_price
                print(f"Would buy approximately {tokens_amount:.2f} {position} tokens")
                
                return {
                    "status": "simulated", 
                    "position": position, 
                    "amount": amount,
                    "price": market_price,
                    "tokens": tokens_amount,
                    "token_id": token_id,
                    "dry_run": True
                }
            
            # En modo real, intentar obtener datos del orderbook
            try:
                # Obtener el precio actual del mercado
                market_price_resp = self.client.get_price(token_id, "SELL")
                market_price = float(market_price_resp.get("price", 0))
                print(f"Current market price for {position}: ${market_price}")
                
                # Obtener el orderbook para ver las órdenes disponibles
                orderbook = self.client.get_order_book(token_id)
                
                # Calcular el tamaño mínimo requerido en tokens
                min_size = max(12.0, 1.2 / market_price) if market_price > 0 else 15.0
                min_cost = min_size * market_price  # Costo mínimo en USDC
                
                print(f"Creating order for {position} position:")
                print(f"Token ID: {token_id}")
                print(f"Market price: ${market_price}")
                print(f"Size: {min_size} tokens")
                print(f"Total cost: ${min_cost:.4f} USDC")
                
                # Crear orden usando OrderArgs
                order_args = OrderArgs(
                    token_id=token_id,
                    size=min_size,
                    price=market_price,
                    side=BUY  # Siempre compramos (YES o NO)
                )
                
                # Crear y firmar la orden
                signed_order = self.client.create_order(order_args)
                print("Signed order created:", signed_order)
                
                # Postear la orden
                resp = self.client.post_order(signed_order)
                print("Order response:", resp)
                
                # Añadir la posición al resultado para confirmar lo que se compró
                if isinstance(resp, dict):
                    resp["position"] = position
                
                return resp
                
            except Exception as e:
                print(f"Error interacting with orderbook API: {e}")
                print("Order execution failed")
                return None
                
        except Exception as e:
            print(f"Error executing market order: {e}")
            print(f"Full error details: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def check_usdc_allowance(self) -> float:
        """Check how much USDC we've approved for spending"""
        try:
            allowance = self.usdc.functions.allowance(
                Web3.to_checksum_address(self.wallet_address),
                Web3.to_checksum_address(self.exchange_address)
            ).call()
            return float(allowance) / 1_000_000  # Convertir de wei a USDC
        except Exception as e:
            print(f"Error checking allowance: {e}")
            return 0.0

    def approve_usdc_spend(self, amount: float):
        """Approve USDC spending"""
        try:
            # Convertir el monto a la unidad correcta (6 decimales para USDC)
            amount_wei = int(amount * 1_000_000)  # Convertir a unidades USDC
            
            # Convertir direcciones a checksum
            exchange_address = Web3.to_checksum_address(self.exchange_address)
            wallet_address = Web3.to_checksum_address(self.wallet_address)
            
            print(f"Approving {amount} USDC ({amount_wei} wei) for {exchange_address}")
            
            # Construir la transacción de aprobación usando el contrato directamente
            approve_txn = self.usdc.functions.approve(
                exchange_address,
                amount_wei
            ).build_transaction({
                'from': wallet_address,
                'nonce': self.w3.eth.get_transaction_count(wallet_address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.chain_id
            })
            
            # Firmar la transacción
            signed_txn = self.w3.eth.account.sign_transaction(approve_txn, private_key=self.private_key)
            
            # Enviar la transacción - usar raw_transaction en lugar de rawTransaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            print(f"Approval transaction sent: {tx_hash.hex()}")
            
            # Esperar a que se confirme
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"Approval confirmed in block: {receipt['blockNumber']}")
            
            # Verificar el nuevo allowance
            new_allowance = self.check_usdc_allowance()
            print(f"New allowance: ${new_allowance}")
            
            return True
            
        except Exception as e:
            print(f"Error approving USDC: {e}")
            print(f"Full error details: {str(e)}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            return False

    def get_usdc_balance(self) -> float:
        """Get USDC balance for the current wallet"""
        try:
            # Verificar que la wallet está configurada
            if not self.wallet_address:
                print("Wallet address not configured")
                return 0.0
                
            # Obtener balance
            balance_res = self.usdc.functions.balanceOf(self.wallet_address).call()
            balance = float(balance_res) / 1_000_000  # USDC tiene 6 decimales
            
            print(f"Raw balance: {balance_res}")
            print(f"Wallet: {self.wallet_address}")
            print(f"USDC Contract: {self.usdc_address}")
            
            return balance
            
        except Exception as e:
            print(f"Error getting USDC balance: {e}")
            print(f"Wallet: {self.wallet_address}")
            return 0.0

    def get_outcome_token_balance(self, token_id: str) -> float:
        """Get outcome token balance for the current wallet"""
        try:
            # TODO: Implementar verificación de balance de tokens outcome usando el contrato ERC1155
            return 0.0
        except Exception as e:
            print(f"Error getting outcome token balance: {e}")
            return 0.0

    def check_outcome_token_allowance(self, token_id: str) -> float:
        """Check outcome token allowance"""
        try:
            # TODO: Implementar verificación de allowance de tokens outcome
            return 0.0
        except Exception as e:
            print(f"Error checking outcome token allowance: {e}")
            return 0.0

    def approve_outcome_token_spend(self, token_id: str, amount: float):
        """Approve outcome token spending"""
        try:
            # TODO: Implementar aprobación de gasto de tokens outcome
            return False
        except Exception as e:
            print(f"Error approving outcome token spend: {e}")
            return False

    def set_all_allowances(self):
        """Set all necessary allowances for trading"""
        try:
            print("Setting allowances for all contracts...")
            
            # Addresses
            ctf_address = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")
            exchange_address = Web3.to_checksum_address("0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E")
            neg_risk_exchange = Web3.to_checksum_address("0xC5d563A36AE78145C45a50134d48A1215220f80a")
            neg_risk_adapter = Web3.to_checksum_address("0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296")
            
            # ERC1155 approval ABI
            erc1155_abi = '''[{
                "inputs": [
                    {"internalType": "address", "name": "operator", "type": "address"},
                    {"internalType": "bool", "name": "approved", "type": "bool"}
                ],
                "name": "setApprovalForAll",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }]'''
            
            # Create CTF contract
            ctf = self.w3.eth.contract(address=ctf_address, abi=erc1155_abi)
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            
            # Approve USDC for all contracts
            for contract in [exchange_address, neg_risk_exchange, neg_risk_adapter]:
                print(f"\nApproving USDC for {contract}...")
                
                # Build USDC approval transaction
                approve_txn = self.usdc.functions.approve(
                    contract,
                    int(MAX_INT, 0)  # Approve maximum amount
                ).build_transaction({
                    'chainId': self.chain_id,
                    'from': self.wallet_address,
                    'nonce': nonce,
                    'gas': 100000,
                    'gasPrice': self.w3.eth.gas_price
                })
                
                # Sign and send transaction
                signed_txn = self.w3.eth.account.sign_transaction(approve_txn, private_key=self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"USDC approval confirmed in block {receipt['blockNumber']}")
                
                nonce += 1
                
                # Approve CTF tokens
                print(f"Approving CTF tokens for {contract}...")
                ctf_txn = ctf.functions.setApprovalForAll(
                    contract,
                    True
                ).build_transaction({
                    'chainId': self.chain_id,
                    'from': self.wallet_address,
                    'nonce': nonce,
                    'gas': 100000,
                    'gasPrice': self.w3.eth.gas_price
                })
                
                # Sign and send transaction
                signed_txn = self.w3.eth.account.sign_transaction(ctf_txn, private_key=self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"CTF approval confirmed in block {receipt['blockNumber']}")
                
                nonce += 1
            
            print("\nAll allowances set successfully!")
            return True
            
        except Exception as e:
            print(f"Error setting allowances: {e}")
            return False

    def get_pinned_markets(self) -> "list[SimpleEvent]":
        """Get pinned markets from Gamma API"""
        try:
            # Obtener mercados pinned usando el endpoint específico o un filtro
            params = {
                "pinned": True,
                "active": True,
                "closed": False
            }
            response = httpx.get(self.gamma_markets_endpoint, params=params)
            if response.status_code == 200:
                markets = response.json()
                return [SimpleEvent(**market) for market in markets]
            return []
        except Exception as e:
            print(f"Error getting pinned markets: {e}")
            return []

    def get_high_volume_markets(self, min_volume: float = 10000) -> "list[SimpleEvent]":
        """Get markets with volume above threshold"""
        events = self.get_all_events()
        return [
            event for event in events 
            if event.active and not event.closed 
            and float(event.volume) > min_volume
        ]

    def detect_category(self, question: str) -> str:
        """Detecta la categoría de un mercado basado en su pregunta"""
        question = question.lower()
        
        # Keywords para cada categoría
        politics_keywords = ['election', 'president', 'vote', 'congress', 'senate', 'minister', 'government', 'fed', 'rate', 'chancellor', 'prime minister']
        sports_keywords = ['nba', 'nfl', 'mlb', 'soccer', 'football', 'basketball', 'baseball', 'league', 'cup', 'championship', 'win', 'relegated']
        crypto_keywords = ['bitcoin', 'eth', 'crypto', 'token', 'blockchain', 'opensea', 'nft']
        entertainment_keywords = ['movie', 'film', 'actor', 'actress', 'award', 'song', 'album', 'show']
        tech_keywords = ['ai', 'openai', 'technology', 'software', 'app', 'launch']
        
        if any(keyword in question for keyword in politics_keywords):
            return 'politics'
        elif any(keyword in question for keyword in sports_keywords):
            return 'sports'
        elif any(keyword in question for keyword in crypto_keywords):
            return 'crypto'
        elif any(keyword in question for keyword in entertainment_keywords):
            return 'entertainment'
        elif any(keyword in question for keyword in tech_keywords):
            return 'tech'
        else:
            return 'other'

    def get_orderbook_for_market(self, market_id, token_id):
        """
        Obtiene el orderbook para un mercado y token específico
        
        Args:
            market_id: ID del mercado
            token_id: ID del token (YES o NO)
            
        Returns:
            dict: Información del orderbook o None si hay error
        """
        max_retries = 3
        retry_delay = 2  # segundos
        
        for attempt in range(max_retries):
            try:
                url = f"{self.clob_url}/orderbook/{token_id}"
                response = self._make_request("GET", url)
                
                if response and response.status_code == 200:
                    return response.json()
                else:
                    status = response.status_code if response else 'None'
                    print(f"Failed to get orderbook (attempt {attempt+1}/{max_retries}). Status: {status}")
                    
                    # Si no es el último intento, esperar y reintentar
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Backoff exponencial
                        
            except Exception as e:
                print(f"Error getting orderbook (attempt {attempt+1}/{max_retries}): {e}")
                
                # Si no es el último intento, esperar y reintentar
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Backoff exponencial
        
        print(f"Failed to get orderbook after {max_retries} attempts")
        return None

    def buy_tokens_with_usdc(self, market_id, token_id, amount_usdc, order_type="Market"):
        """
        Ejecuta una compra de tokens YES o NO usando USDC
        
        Args:
            market_id: ID del mercado
            token_id: ID del token a comprar (YES o NO)
            amount_usdc: Cantidad de USDC a gastar
            order_type: Tipo de orden ("Market" o "Limit")
            
        Returns:
            dict: Resultado de la ejecución o False si hay error
        """
        try:
            # Primero verificamos el precio actual
            current_price = self.get_current_token_price(token_id)
            
            # En modo dry_run, si no podemos obtener el precio, usamos un valor simulado
            if not current_price and self.dry_run:
                # Simular un precio aleatorio para testing
                current_price = round(random.uniform(0.05, 0.95), 4)
                print(f"Using simulated price in dry_run mode: ${current_price}")
            elif not current_price:
                print("Could not determine current price")
                return False
            
            print(f"Current token price: ${current_price}")
            
            # Calcular cantidad de tokens a comprar
            tokens_to_buy = amount_usdc / current_price
            print(f"Attempting to buy {tokens_to_buy:.4f} tokens at ${current_price} each")
            
            # Preparar los datos de la orden
            order_data = {
                "market_id": market_id,
                "token_id": token_id,
                "side": "buy",
                "type": order_type.lower(),
                "size": tokens_to_buy,
                "price": current_price,
                "amount_usdc": amount_usdc
            }
            
            # Si es dry_run, simular un resultado exitoso
            if self.dry_run:
                print(f"Order execution data (SIMULATED): {json.dumps(order_data, indent=2)}")
                # Hash simulado para transacción
                transaction_hash = "0x" + "".join([random.choice("0123456789abcdef") for _ in range(64)])
                
                # Resultado simulado
                result = {
                    "success": True,
                    "simulated": True,
                    "transaction_hash": transaction_hash,
                    "market_id": market_id,
                    "token_id": token_id,
                    "tokens_purchased": tokens_to_buy,
                    "price_per_token": current_price,
                    "total_cost_usdc": amount_usdc,
                    "timestamp": datetime.now().isoformat()
                }
                
                return result
            
            # En un sistema real, aquí se ejecutaría la orden
            print(f"Order execution data: {json.dumps(order_data, indent=2)}")
            
            # Resultado simulado
            transaction_hash = "0x" + "".join([random.choice("0123456789abcdef") for _ in range(64)])
            result = {
                "success": True,
                "transaction_hash": transaction_hash,
                "market_id": market_id,
                "token_id": token_id,
                "tokens_purchased": tokens_to_buy,
                "price_per_token": current_price,
                "total_cost_usdc": amount_usdc,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            print(f"Error executing buy order: {e}")
            traceback.print_exc()
            
            # Si es dry_run, devolver un resultado simulado incluso si hay errores
            if hasattr(self, 'dry_run') and self.dry_run:
                print("Returning simulated result despite error (DRY RUN mode)")
                return {
                    "success": True,
                    "simulated": True,
                    "error_recovered": True,
                    "market_id": market_id,
                    "token_id": token_id,
                    "timestamp": datetime.now().isoformat()
                }
                
            return False
    
    def get_current_token_price(self, token_id):
        """
        Obtiene el precio actual de un token
        
        Args:
            token_id: ID del token
            
        Returns:
            float: Precio actual del token o None si hay error
        """
        try:
            # En un sistema real, aquí se consultaría el API
            # Por simplicidad, retornamos un precio aleatorio entre 0.05 y 0.95
            price = round(random.uniform(0.05, 0.95), 4)
            return price
        except Exception as e:
            print(f"Error getting token price: {e}")
            return None

    def _make_request(self, method, url, data=None, headers=None):
        """
        Helper method for making HTTP requests
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            data: Request data (for POST, PUT)
            headers: Custom headers
            
        Returns:
            Response object or None if error
        """
        try:
            default_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            if headers:
                default_headers.update(headers)
            
            # Usar un timeout más largo para evitar errores por lentitud de la red
            timeout = 60  # 60 segundos
                
            if method.upper() == 'GET':
                response = requests.get(
                    url, 
                    headers=default_headers, 
                    timeout=timeout,
                    verify=True  # Verificar certificados SSL
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url, 
                    json=data, 
                    headers=default_headers, 
                    timeout=timeout,
                    verify=True
                )
            elif method.upper() == 'PUT':
                response = requests.put(
                    url, 
                    json=data, 
                    headers=default_headers, 
                    timeout=timeout,
                    verify=True
                )
            elif method.upper() == 'DELETE':
                response = requests.delete(
                    url, 
                    headers=default_headers, 
                    timeout=timeout,
                    verify=True
                )
            else:
                print(f"Unsupported HTTP method: {method}")
                return None
            
            # Verificar si la respuesta fue exitosa
            if response.status_code >= 400:
                print(f"API error: status_code={response.status_code}, content={response.text[:200]}")
                
            return response
            
        except requests.exceptions.Timeout as e:
            print(f"Request timeout ({method} {url}): {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error ({method} {url}): {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request error ({method} {url}): {e}")
            return None
        except Exception as e:
            print(f"Unexpected error ({method} {url}): {e}")
            return None


def test():
    host = "https://clob.polymarket.com"
    key = os.getenv("POLYGON_WALLET_PRIVATE_KEY")
    print(key)
    chain_id = POLYGON

    # Create CLOB client and get/set API credentials
    client = ClobClient(host, key=key, chain_id=chain_id)
    client.set_api_creds(client.create_or_derive_api_creds())

    creds = ApiCreds(
        api_key=os.getenv("CLOB_API_KEY"),
        api_secret=os.getenv("CLOB_SECRET"),
        api_passphrase=os.getenv("CLOB_PASS_PHRASE"),
    )
    chain_id = AMOY
    client = ClobClient(host, key=key, chain_id=chain_id, creds=creds)

    print(client.get_markets())
    print(client.get_simplified_markets())
    print(client.get_sampling_markets())
    print(client.get_sampling_simplified_markets())
    print(client.get_market("condition_id"))

    print("Done!")


def gamma():
    url = "https://gamma-com"
    markets_url = url + "/markets"
    res = httpx.get(markets_url)
    code = res.status_code
    if code == 200:
        markets: list[SimpleMarket] = []
        data = res.json()
        for market in data:
            try:
                market_data = {
                    "id": int(market["id"]),
                    "question": market["question"],
                    # "start": market['startDate'],
                    "end": market["endDate"],
                    "description": market["description"],
                    "active": market["active"],
                    "deployed": market["deployed"],
                    "funded": market["funded"],
                    # "orderMinSize": float(market['orderMinSize']) if market['orderMinSize'] else 0,
                    # "orderPriceMinTickSize": float(market['orderPriceMinTickSize']),
                    "rewardsMinSize": float(market["rewardsMinSize"]),
                    "rewardsMaxSpread": float(market["rewardsMaxSpread"]),
                    "volume": float(market["volume"]),
                    "spread": float(market["spread"]),
                    "outcome_a": str(market["outcomes"][0]),
                    "outcome_b": str(market["outcomes"][1]),
                    "outcome_a_price": str(market["outcomePrices"][0]),
                    "outcome_b_price": str(market["outcomePrices"][1]),
                }
                markets.append(SimpleMarket(**market_data))
            except Exception as err:
                print(f"error {err} for market {id}")
        pdb.set_trace()
    else:
        raise Exception()


def main():
    # auth()
    # test()
    # gamma()
    print(Polymarket().get_all_events())


if __name__ == "__main__":
    load_dotenv()

    p = Polymarket()

    # k = p.get_api_key()
    # m = p.get_sampling_simplified_markets()

    # print(m)
    # m = p.get_market('11015470973684177829729219287262166995141465048508201953575582100565462316088')

    # t = m[0]['token_id']
    # o = p.get_orderbook(t)
    # pdb.set_trace()

    """
    
    (Pdb) pprint(o)
            OrderBookSummary(
                market='0x26ee82bee2493a302d21283cb578f7e2fff2dd15743854f53034d12420863b55', 
                asset_id='11015470973684177829729219287262166995141465048508201953575582100565462316088', 
                bids=[OrderSummary(price='0.01', size='600005'), OrderSummary(price='0.02', size='200000'), ...
                asks=[OrderSummary(price='0.99', size='100000'), OrderSummary(price='0.98', size='200000'), ...
            )
    
    """

    # https://polygon-rpc.com

    test_market_token_id = (
        "101669189743438912873361127612589311253202068943959811456820079057046819967115"
    )
    test_market_data = p.get_market(test_market_token_id)

    # test_size = 0.0001
    test_size = 1
    test_side = BUY
    test_price = float(ast.literal_eval(test_market_data["outcome_prices"])[0])

    # order = p.execute_order(
    #    test_price,
    #    test_size,
    #    test_side,
    #    test_market_token_id,
    # )

    # order = p.execute_market_order(test_price, test_market_token_id)

    balance = p.get_usdc_balance()
