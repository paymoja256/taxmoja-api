import base64
from base64 import b64decode, b64encode
from urllib import response
import uuid
import json
import zlib
import ast
import datetime
import pytz
import structlog
from OpenSSL import crypto
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_v1_5
import os
from fastapi import HTTPException
from app.api.handlers.UG.base import EfrisBase
from app.models.stock_dal import get_stock_by_goods_code, create_stock, get_branch_by_client_id, create_stock_branch
from app.db.schemas.stock import IncomingGoodsStockAdjustmentSchema, IncomingStockConfigurationSchema, BranchSchema
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.Padding import unpad
import base64


struct_logger = structlog.get_logger(__name__)

BS = 16


def pad(s): return s + (BS - len(s) % BS) * chr(BS - len(s) % BS)


def unpad(s): return s[0:-ord(s[-1])]


class EFRIS(EfrisBase):

    def __init__(self, settings):
        struct_logger.info(
            event='EFRIS', message='API Initialised', settings=settings)

        self.settings = settings

        if settings['online_mode']:

            self.url = settings['efris_url_online']
            struct_logger.info(
                event='EFRIS', message='using online mode', url=self.url)
        else:

            self.url = settings['efris_url']
            struct_logger.info(
                event='EFRIS', message='using offline mode', url=self.url)
        self.interface_code = ''
        self.request_message = ''
        self.headers = ''
        self.t_pin = settings['tax_pin']
        self.data = {}
        self.key_table = ''
        # efris_client.datasource  # 101:efd 102:cs 103:webService api 104:BS
        self.data_source = "101"
        # 101 General Industry 102 Export; 103 Import; 104
        self.industry_code = settings['industry_code']
        self.appid = settings['app_id']
        self.version = settings['efris_version']  # efris_client.efris_version
        self.exchange_id = uuid.uuid4().hex
        self.mac_address = hex(uuid.getnode())
        self.user_name = settings['efris_username']
        self.device_no = settings['efris_device_no']
        self.tax_payer_id = settings['efris_tax_payer_id']
        self.private_key = os.path.abspath(
            'app/api/handlers/UG/keys/{}/key.p12'.format(self.tax_payer_id))
        self.private_key_password = settings['private_key_password']
        self.public_key = ''
        self.aes_password = ''
        self.signature = ''
        self.server_time = ''
        self.api_response = ''

    async def efris_request_data(self, content='', signature=''):

        request_data = {
            "data": {
                "content": content,
                "signature": signature,
                "dataDescription": {
                    "codeType": "1",
                    "encryptCode": "1",
                    "zipCode": "0"
                }
            },
            "globalInfo": {
                "appId": self.appid,
                "version": self.version,
                "dataExchangeId": self.exchange_id,
                "interfaceCode": self.interface_code,
                "requestCode": "TP",
                "requestTime": self.get_request_time(),
                "responseCode": "TA",
                "userName": self.user_name,
                "deviceMAC": self.mac_address,
                "deviceNo": self.device_no,
                "tin": self.t_pin,
                "brn": "",
                "taxpayerID": self.tax_payer_id,
                "longitude": "116.397128",
                "latitude": "39.916527",
                "extendField": {
                    "responseDateFormat": "dd/MM/yyyy",
                    "responseTimeFormat": "dd/MM/yyyy HH:mm:ss"
                }
            },
            "returnStateInfo": {
                "returnCode": "",
                "returnMessage": ""
            }
        }
        response = await self.api_request('post', request_data)
        struct_logger.info(event='efris_request_data',
                           message="sending efris api request",
                           response=response

                           )
        try:
            return response.json()
        except Exception as e:
            struct_logger.error(event='efris_request_data',
                                message="failed to decode response",
                                response=response,
                                error=e
                                )
            return response

    async def get_server_time(self):
        """The EFD time is synchronized with the server time."""
        self.interface_code = 'T101'
        return await self.efris_request_data()

    async def get_key_signature(self):
        """Get symmetric key and signature information
        1. The client gets a symmetric key every time you log in, and all subsequent encryption is encrypted by symmetric key.
        2. The server randomly generates an 8-bit symmetric key and a signature value for encryption.
        not working
        """
        self.interface_code = 'T104'
        self.api_response = await self.efris_request_data(content='', signature='')

        try:
            data = json.loads(b64decode(self.api_response['data']['content']))
            self.aes_password = self.key_decryption2(
                b64decode(data['passowrdDes']))

            self.signature = data['sign']
            struct_logger.info(event="get_key_signature",
                               aes_password=self.aes_password, signature=self.signature)
            return self.aes_password
        except Exception as ex:

            struct_logger.info(event="get_key_signature",
                               message="failed to decode response", error=str(ex))

            return self.api_response

    async def normal_invoice_query(self, invoice_no="", device_no="", invoice_type=""):
        """Query all Invoice/Receipt invoice information that can be issued with Credit Note, Cancel Debit Note"""
        self.interface_code = 'T107'
        data = {
            "invoiceNo": invoice_no,
            "deviceNo": device_no,
            "buyerTin": "",
            "buyerLegalName": "",
            "invoiceType": invoice_type,
            "startDate": "",
            "endDate": "",
            "pageNo": "1",
            "pageSize": "20",
            "branchName": ""
        }

        return await self.efris_request_data(content=self.clean_data(data))

    async def goods_inquiry(self, db, goods_code=""):
        """Goods/Services Inquiry: return commodity data using the goods code"""
        # Try getting the good from the database
        db_good = get_stock_by_goods_code(db, goods_code)

        if db_good and db_good.goods_tax_id:
            stock_details = {
                "goodsName": db_good.goods_name,
                "goodsCode": db_good.goods_code,
                "unitPrice": db_good.unit_price,
                "measureUnit": db_good.measure_unit,
                "currency": db_good.currency,
                "commodityCategoryCode": db_good.commodity_tax_category_code,
                "commodityCategoryName": db_good.commodity_tax_category_name,
                "id": db_good.goods_tax_id,
                "isExempt": db_good.is_exempt,
                "isZeroRate": db_good.is_zero_rate,
                "taxRate": db_good.tax_rate,
                "remarks": db_good.remarks,
                "client_id": db_good.client_id
            }
            struct_logger.info(event="goods_inquiry",
                               db_response=stock_details)
            return True, stock_details

        self.interface_code = "T127"
        data = {
            "goodsCode": goods_code,
            "goodsName ": "",
            "commodityCategoryName": "",
            "pageNo": "1",
            "pageSize": "10"
        }

        api_response = await self.online_mode_request(data)

        if api_response.get('records', None):
            goods_details = api_response['records'][0]
            struct_logger.info(event="goods_inquiry",
                               api_response=goods_details, request=data)
            # stock_details = {
            #     "goods_name": goods_details["goodsName"],
            #     "goods_code": goods_details["goodsCode"],
            #     "unit_price": goods_details["unitPrice"],
            #     "measure_unit": goods_details["measureUnit"],
            #     "currency": goods_details["currency"],
            #     "ura_commodity_category_code": goods_details["commodityCategoryCode"],
            #     "ura_commodity_category_name": goods_details["commodityCategoryName"],
            #     "goods_description": goods_details["commodityCategoryName"],
            #     "ura_goods_id": goods_details["id"],
            #     "is_zero_rate": goods_details["isZeroRate"],
            #     "is_exempt": goods_details["isExempt"],
            #     "tax_rate": goods_details["taxRate"],
            #     "remarks": goods_details["goodsName"],
            #     "client_id": self.settings["tax_pin"]
            # }
            # stock_details_base = IncomingStockConfigurationSchema(**stock_details)
            # create_stock(db, stock_details_base)

            return True, goods_details
        else:
            msg = "Item with code {} not found".format(goods_code)
            struct_logger.error(event="goods_inquiry", error=msg,
                                api_response=api_response, request=data)

            return False, msg

    async def get_all_branches(self, db):
        """Get all branches"""
        branch = get_branch_by_client_id(db, self.settings["tax_pin"])
        if branch:
            struct_logger.info(
                event="get_all_branches", api_response=branch.branch_id, message="database entry")
            return branch.branch_id

        self.interface_code = "T138"
        api_response = await self.efris_request_data(content='', signature='')
        branches = self.decrypt_api_response(api_response)
        struct_logger.info(event="get_all_branches", api_response=api_response)

        for branch in branches:
            data = {

                "client_id": self.settings["tax_pin"],
                "branch_name": branch['branchName'],
                "branch_id": branch['branchId']
            }
            branch_base = BranchSchema(**data)
            create_stock_branch(db, branch_base)
        return branches[0]['branchId']

    async def goods_upload(self, data):
        """Goods Upload: Module used for goods upload"""
        self.interface_code = "T130"
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="goods_upload",
                           api_response=api_response, request=data)
        return api_response

    async def goods_stock_in(self, db, goods_detail: IncomingGoodsStockAdjustmentSchema):
        """Goods Stock Maintain"""
        code = goods_detail.goods_code
        proceed, goods_configuration = await self.goods_inquiry(db, code)
        branch_id = await self.get_all_branches(db)
        stock_in_date = datetime.date.today().strftime("%Y-%m-%d")
        if proceed:
            struct_logger.info(
                event="goods_stock_in", message="goods details found for code:{} ".format(code))

            self.interface_code = "T131"
            data = {
                "goodsStockIn": {
                    "operationType": goods_detail.operation_type,
                    "supplierTin": goods_detail.supplier_tin,
                    "supplierName": goods_detail.supplier,
                    "adjustType": goods_detail.adjust_type,
                    "remarks": goods_detail.purchase_remarks,
                    "stockInDate": stock_in_date,
                    "stockInType": goods_detail.stock_in_type,
                    "productionBatchNo": "",
                    "productionDate": "",
                    "branchId": branch_id
                },
                "goodsStockInItem": [
                    {
                        "commodityGoodsId": goods_configuration["id"],
                        "goodsCode": goods_detail.goods_code,
                        "measureUnit": goods_configuration["measureUnit"],
                        "quantity": goods_detail.quantity,
                        "unitPrice": goods_detail.purchase_price
                    }
                ]
            }
            api_response = await self.online_mode_request(data)
            struct_logger.info(event="goods_stock_in",
                               api_response=api_response, request=data)
            return api_response
        message = "goods details not found for code:{} ".format(code)
        struct_logger.info(event="goods_stock_in", message=message)
        return {"returnMessage": message}

    async def all_invoice_query(self, reference_no=""):
        """Query all invoice information(Invoice/receipt, credit note, debit note, cancel credit note, cancel debit
        note) """
        self.interface_code = 'T106'
        data = {
            "oriInvoiceNo": "",
            "invoiceNo": "",
            "deviceNo": "",
            "buyerTin": "",
            "buyerNinBrn": "",
            "buyerLegalName": "",
            "combineKeywords": "",
            "invoiceType": "",
            "invoiceKind": "1",
            "isInvalid": "",
            "isRefund": "",
            "startDate": "",
            "pageNo": "1",
            "pageSize": "20",
            "referenceNo": reference_no,
            "branchName": ""
        }

        api_response = await self.online_mode_request(data)
        struct_logger.info(event="all_invoice_query",
                           reference_no=reference_no, response=api_response)
        return api_response['records'][0]

    async def get_invoice_details(self, invoice_number):
        """Invoice details are queried according to Invoice number."""
        self.interface_code = 'T108'
        data = {
            "invoiceNo": invoice_number
        }
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="get_invoice_details",
                           api_response=api_response, request=data)
        return api_response

    async def send_invoice(self, data):
        """Upload the Invoice/Receipt or Debit Note to the server."""
        self.interface_code = 'T109'
        # response = b64decode(api_response['data']['content'])
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="efris_send_invoice",
                           api_response=api_response)
        return api_response

    async def credit_note_upload(self, data):
        """Credit note upload"""
        self.interface_code = 'T110'
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="credit_note_upload",
                           api_response=api_response, request=data)
        return api_response

    async def credit_debit_query(self):
        """Credit/Cancel Debit Note Application List Query"""
        self.interface_code = 'T111'
        data = {
            "referenceNo": "",
            "oriInvoiceNo": "",
            "invoiceNo": "",
            "combineKeywords": "",
            "approveStatus": "",
            "queryType": "1",
            "invoiceApplyCategoryCode": "",
            "startDate": "",
            "endDate": "",
            "pageNo": "1",
            "pageSize": "20"
        }
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="credit_debit_query",
                           api_response=api_response, request=data)
        return api_response

    async def credit_note_status(self, data):
        """credit application details"""
        self.interface_code = 'T112'
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="credit_note_status",
                           api_response=api_response, request=data)
        return api_response

    async def credit_note_approval(self, data):
        """credit application approval"""
        self.interface_code = 'T113'
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="credit_note_approval",
                           api_response=api_response, request=data)
        return api_response

    async def credit_note_cancellation(self, original_invoice_id, invoice_number, reason_code='101',
                                       invoice_category_code='104'):
        """Cancel Credit Note initiate Cancel of Debit Note Application"""
        self.interface_code = 'T114'
        data = {
            "oriInvoiceId": original_invoice_id,
            "invoiceNo": invoice_number,
            "reason": "",
            "reasonCode": reason_code,
            "invoiceApplyCategoryCode": invoice_category_code
        }
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="credit_note_cancellation",
                           api_response=api_response, request=data)
        return api_response

    async def update_efris_dictionary(self):
        """Query system parameters such as VAT, Excise Duty, and Currency"""

        self.interface_code = 'T115'
        api_response = await self.online_mode_request_unzip(self.data)
        struct_logger.info(event="update_efris_dictionary",
                           api_response=api_response, request=self.data)
        return api_response

    async def z_report_upload(self):
        """Z-report Daily Upload"""
        self.interface_code = 'T116'
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="z_report_upload",
                           api_response=api_response, request=self.data)
        return api_response

    async def invoice_check(self, data):
        """Contrast client invoice with server invoice consistent"""
        self.interface_code = 'T117'
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="invoice_check",
                           api_response=api_response, request=data)
        return api_response

    async def query_credit_note(self, data):
        """Query Credit Note and Cancel Debit Note to apply for details"""
        self.interface_code = 'T118'
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="query_credit_note",
                           api_response=api_response, request=data)
        return api_response

    async def query_tax_payer(self, tin=None, nin=None):
        """Query Taxpayer Information By TIN or ninBrn"""
        self.interface_code = 'T119'
        self.data = {"tin": tin, "ninBrn": nin}
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="query_tax_payer",
                           api_response=api_response, request=self.data)
        return api_response

    async def void_credit_note(self, bus_key, ref_no):
        """Void Credit Debit/Note Application"""
        self.interface_code = 'T120'
        self.data = {
            "businessKey": bus_key, "referenceNo": ref_no
        }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="void_credit_note",
                           api_response=api_response, request=self.data)
        return api_response

    async def get_exchange_rate(self, currency):
        """Acquiring exchange rate"""
        self.interface_code = 'T121'
        self.data = {
            "currency": currency
        }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="get_exchange_rate",
                           api_response=api_response, request=self.data)
        return api_response

    async def query_cancellation_credit_note(self, invoice_number):
        """Query cancel credit note details Mapping to T114"""
        self.interface_code = "T122"
        self.data = {
            "invoiceNo": invoice_number
        }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="query_cancellation_credit_note",
                           api_response=api_response, request=self.data)
        return api_response

    async def query_commodity_category(self):
        self.interface_code = "T124"
        self.data = {"pageNo": "1",
                     "pageSize": "100"
                     }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="query_commodity_category",
                           api_response=api_response, request=self.data)
        return api_response

    async def query_excise_duty(self):
        """Query Excise Duty"""
        self.interface_code = "T125"
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="query_excise_duty",
                           api_response=api_response, request=self.data)
        return api_response

    async def get_all_exchange_rates(self):
        """get all exchange rates"""
        self.interface_code = "T126"
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="get_all_exchange_rates",
                           api_response=api_response, request=self.data)
        return api_response

    async def stock_quantity_by_goods_id(self, goods_code=""):
        """Goods/Services Inquiry"""
        proceed, good_details = await self.goods_inquiry(goods_code)
        self.interface_code = "T128"
        self.data = {
            "id": good_details['id'],
            "branchId": ""
        }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="stock_quantity_by_goods_id",
                           api_response=api_response, request=self.data)
        return api_response

    async def batch_invoice_upload(self, data):
        """Batch Invoice Upload"""
        self.interface_code = "T129"
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="batch_invoice_upload",
                           api_response=api_response, request=data)
        return api_response

    async def upload_exception_log(self, code, desc, error, time):
        """Upload exception log"""
        self.interface_code = "T132"
        self.data = [{
            "interruptionTypeCode": code, "description": desc,
            "errorDetail": error, "interruptionTime": time
        }]
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="upload_exception_log",
                           api_response=api_response, request=self.data)
        return api_response

    async def upgrade_system_file_download(self, version, os_type):
        """Query the files needed to upgrade the system by version number and operation type number, including
        uploading attachments and required sql files! """

        self.interface_code = "T133"
        self.data = {
            "tcsVersion": version,
            "osType": os_type
        }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="upgrade_system_file_download",
                           api_response=api_response, request=self.data)
        return api_response

    async def commodity_category_incremental_update(self, data):
        """Returns only the commodity category changes since the local version up to current version."""
        self.interface_code = "T134"
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="commodity_category_incremental_update",
                           api_response=api_response, request=data)
        return api_response

    async def get_tcs_latest_version(self):
        """Get Tcs Latest Version"""
        self.interface_code = "T135"
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="get_tcs_latest_version",
                           api_response=api_response, request=self.data)
        return api_response

    async def public_key_certificate_upload(self, filename, verify_str, file_content):
        """Certificate public key upload"""
        self.interface_code = "T136"
        self.data = {
            "fileName": filename,
            "verifyString": verify_str,
            "fileContent": file_content
        }
        api_response = await self.online_mode_request(self.data)
        struct_logger.info(event="public_key_certificate_upload",
                           api_response=api_response, request=self.data)
        return api_response

    async def check_exempt_taxpayer(self, data):
        """Check whether the taxpayer is tax exempt/Deemed"""
        self.interface_code = "T137"
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="check_exempt_taxpayer",
                           api_response=api_response, request=data)
        return api_response

    async def goods_stock_transfer(self, data):
        """Stock Transfer"""
        self.interface_code = "T139"
        api_response = await self.online_mode_request(data)
        struct_logger.info(event="goods_stock_transfer",
                           api_response=api_response, request=data)
        return api_response

    async def online_mode_request(self, data):
        encrypted_content = self.aes_encryption(json.dumps(data))
        signature = self.sign_data(encrypted_content)
        api_response = await self.efris_request_data(content=encrypted_content, signature=signature)
        struct_logger.info(event="online_mode_request",
                           api_response=api_response)

        decrypted_api_response = self.decrypt_api_response(api_response)

        if decrypted_api_response:
            struct_logger.info(event="online_mode_request",
                               decrypted_api_response=api_response, request=data)
            return decrypted_api_response

        return api_response

    async def online_mode_request_unzip(self, data):

        encrypted_content = self.aes_encryption(json.dumps(data))
        signature = self.sign_data(encrypted_content)
        api_response = await self.efris_request_data(content=encrypted_content, signature=signature)
        api_response = b64decode(api_response['data']['content'].encode())
        # api_response = self.un_zip_data(api_response)
        struct_logger.info(event=" online_mode_request_unzip", response=type(
            api_response), api_response=api_response)

        return api_response

    def decrypt_api_response(self, api_response):
        try:
            content = api_response['data']['content']
            decrypted_content = self.aes_decryption(content)
            return decrypted_content
        except (KeyError, IndexError) as ex:

            struct_logger.error(event="decrypt_efris_api_response", error='content missing or empty',
                                api_response=api_response)

            return api_response

    def retrieve_private_key_old(self):
        p12 = crypto.load_pkcs12(
            open(self.private_key, 'rb').read(), self.private_key_password)
        return crypto.dump_privatekey(crypto.FILETYPE_PEM, p12.get_privatekey())

    def retrieve_private_key(self):
        with open(self.private_key, "rb") as pfx_file:
            pfx_data = pfx_file.read()

        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data, self.private_key_password.encode()
        )

        if private_key is None:
            raise ValueError("No private key found in the PKCS#12 file")

        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()  # No password on private key
        )

    def key_decryption(self, str_to_decrypt):
        rsa_key = RSA.importKey(self.retrieve_private_key())
        cipher = PKCS1_v1_5.new(rsa_key)
        return cipher.decrypt(str_to_decrypt, self.aes_password).decode()

    def key_decryption2(self, str_to_decrypt):
        # Step 1: Decrypt the AES key using RSA
        # Your private RSA key
        rsa_key = RSA.importKey(self.retrieve_private_key())
        cipher_rsa = PKCS1_v1_5.new(rsa_key)

        # Decode the Base64 ciphertext and use RSA to decrypt it
        return cipher_rsa.decrypt(str_to_decrypt, None).decode()

        # Step 2: Decrypt the actual data using AES
        # cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv=self.iv)  # Ensure 'self.iv' is available, or pass it
        # decrypted_data = unpad(cipher_aes.decrypt(self.ciphertext), AES.block_size)

        # return decrypted_data.decode()  # Return the decrypted data as a string

    def aes_encryption(self, content):
        content = pad(content)
        cipher = AES.new(b64decode(self.aes_password), AES.MODE_ECB)
        return b64encode(cipher.encrypt(content.encode('utf8'))).decode("utf-8")

    def aes_decryption(self, str_to_decrypt):
        cipher = AES.new(b64decode(self.aes_password), AES.MODE_ECB)
        content = cipher.decrypt(b64decode(str_to_decrypt))
        try:
            return json.loads(unpad(content.decode("utf-8")))
        except Exception:

            struct_logger.info(event="aes_decryption", msg=str(type(content)))
        
            return unpad(content.decode("utf-8"))

    def sign_data_old(self, content):
        p12 = crypto.load_pkcs12(
            open(self.private_key, 'rb').read(), self.private_key_password)
        priv_key = p12.get_privatekey()
        signature_bin_str = crypto.sign(priv_key, content, 'sha1')
        return b64encode(signature_bin_str).decode("utf-8")

    def sign_data(self, content):
        with open(self.private_key, "rb") as pfx_file:
            pfx_data = pfx_file.read()

        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data, self.private_key_password.encode()
        )

        if private_key is None:
            raise ValueError("No private key found in the PKCS#12 file")

        signature = private_key.sign(
            content.encode(),  # Ensure content is in bytes
            padding.PKCS1v15(),
            hashes.SHA1()
        )

        return b64encode(signature).decode("utf-8")

    @staticmethod
    def un_zip_data(data):
        return zlib.decompress(data, 16 + zlib.MAX_WBITS)

    @staticmethod
    def zip_data(data):
        return zlib.compress(data)

    @staticmethod
    def string_eval(content):
        try:
            content = ast.literal_eval(content)
            return content
        except ValueError:
            # corrected = "\'" + content + "\'"
            content = ast.eval(content)
            return content

    @staticmethod
    def clean_data(data):
        return b64encode(json.dumps(data).encode('utf-8')).decode('utf8')

    @staticmethod
    def get_request_time():
        """Returns the request time for the API"""

        return datetime.datetime.now(tz=pytz.timezone('Africa/Kampala')).strftime("%Y-%m-%d %H:%M:%S.%f")


class EFRISException(Exception):

    def __init__(self, response, send_request):
        self.response = response
        self.send_request = send_request
        super(EFRISException, self).__init__(self.send_request, self.response)
