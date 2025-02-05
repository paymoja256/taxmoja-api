import base64
import hashlib
import os
from ctypes import cdll, create_string_buffer, byref
import pathlib
from random import randint
import simplejson as json
import Padding
import structlog
from Crypto.Cipher import DES
from app.api.handlers.ZM.base import ZraBase


struct_logger = structlog.get_logger(__name__)


class DataEncryption:
    """This class is used for encryption and decryption of content sent to and fro ZRA using the random DES key"""

    def __init__(self, key):
        self.cipher = DES.new(key, DES.MODE_ECB)
        self.hash = hashlib.md5()

    @staticmethod
    def pad(data):
        return Padding.appendNullPadding(data, 8).encode()

    @staticmethod
    def un_pad(data):
        return Padding.removeNullPadding(data, 8)

    def content_sign(self, data):
        self.hash.update(data)
        b_64 = base64.b64encode(self.hash.digest())
        return b_64.decode()

    def des_encrypt_64encode(self, data):
        data_encrypt = self.cipher.encrypt(data)
        return base64.b64encode(data_encrypt)

    def des_decrypt_64encode(self, data):
        data = base64.b64decode(data)
        data_decrypt = self.cipher.decrypt(data)
        return json.loads(data_decrypt.decode('utf-8').rstrip('\x00'))
        # return data_decrypt.rstrip('\x00')

    def encrypted_content(self, data):
        data = self.pad(data)  # add padding
        data = self.des_encrypt_64encode(data)  # DES encrypt data
        return data.decode()  # convert from bytes to string


class FiscalCode:
    """This class contains 'get_fiscal_code' method for generating fiscal code.
    C++ DLL file which must be provided during initialization of the class.

    When the class is initialized, a 20 bytes buffer is created in memory which the 'get_fiscal_code' method
    uses as storage for fiscal code calculation.
    """

    def __init__(self, dll_file):

        """:param dll_file: DLL file location
        """

        if not os.path.exists(dll_file):
            raise Exception('DLL file cannot be found{}'.format(dll_file))

        self.my_dll = cdll.LoadLibrary(dll_file)
        self.fiscal_code = create_string_buffer(b'\000' * 20)  # create 20-bytes buffer in memory

    def get_fiscal_code(self, tpin, inv_code, inv_num, inv_time, terminal_id, amount, pri_key):
        """Calculates fiscal code

        :param tpin: business TPIN (type: string)
        :param inv_code: invoice code (type: string)
        :param inv_num: invoice number (type: string)
        :param inv_time: invoicing time. this should be Zambia local time. (type: string)
        :param terminal_id:terminal ID (type: string)
        :param amount: amount  (type: string)
        :param pri_key: private key (type: string)
        :return: fiscal code bytes
        """
        if len(tpin) != 18 or len(terminal_id) != 12 or len(inv_code) != 12 or \
                len(inv_num) != 8 or len(inv_time) != 14 or len(amount) != 20:
            raise Exception("Invalid length for an input argument")

        pri_key_b64decode = base64.b64decode(pri_key)

        self.my_dll.GetFiscalCode(tpin.encode(), inv_code.encode(), inv_num.encode(), inv_time.encode(),
                                  terminal_id.encode(), amount.encode(), byref(self.fiscal_code),
                                  pri_key_b64decode,
                                  len(pri_key_b64decode))

        return self.fiscal_code.value


class ZRA(ZraBase):
    def __init__(self, settings):
        struct_logger.info(event='ZRA', message='API Initialised', settings=settings)
        self.software_version = settings['software_version']
        self.terminal_id = settings['zra_terminal_id']
        self.business_data = json.dumps({"id": self.terminal_id})
        self.url = settings['zra_url']
        self.serial_number = settings['zra_serial_number']
        self.registration_code = settings['zra_registration_code']
        self.tax_pin = settings['zra_tax_pin']
        self.tax_account_name = settings['zra_tax_acc_name']
        self.bus_id = "INVOICE-REPORT-R"
        self.key = '12908415'.encode()
        self.zra_private_key = settings['zra_private_key']
        self.signed_rsa_key = settings['zra_signed_rsa_key']
        self.device = self.terminal_id
        self.serial = randint(100000, 999999)
        self.enc = DataEncryption(self.key)
        self.timestamp = ''
        current_path=pathlib.Path(__file__).parent.resolve()
        self.dll = "{}/libFiscalCode64.so".format(current_path)
        
        self.fiscal_code_obj = FiscalCode(self.dll)
        self.headers = {
            'Content-Type': "application/json;Charset=utf-8",
            'Host': "211.90.56.2",
            # 'Content-Length': "1300"
        }
        self.content = ''
        self.sign = ''
        self.api_response = {}
        self.data = {}

    async def zra_request_data(self):
        self.content = self.enc.encrypted_content(self.business_data)
        self.sign = self.enc.content_sign(self.content.encode())
        request_data = {"message": {"body": {
            "data": {"device": self.device,
                     "serial": self.serial,
                     "bus_id": self.bus_id,
                     "content": self.content,
                     "sign": self.sign,
                     "key": self.signed_rsa_key
                     }
        }
        }
        }

        response = await self.api_request('post', request_data)
        struct_logger.info(event='zra_request_data',
                           message="sending zra api request",
                           content=self.business_data,
                           interface=self.bus_id,
                           response=response.json()
                           )
        return response.json()

    def process_zra_response(self, response):
        try:
            api_content = response['message']['body']['data']['content']  # encrypted content from ZRA
            enc_key = response['message']['body']['data']['key']  # encrypted key sent by ZRA
            if self.bus_id == "R-R-01":
                response = self.enc.des_decrypt_64encode(api_content)

            else:
                dec_key = self.rsa_des_key_decrypt(enc_key)  # decrypt the key sent by ZRA
                dec = DataEncryption(dec_key)
                response = dec.des_decrypt_64encode(api_content)

            return True, response
        except Exception as ex:
            return False, str(ex)

    def rsa_des_key_decrypt(self, message):
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        from base64 import b64decode
        str_private_key = "-----BEGIN PRIVATE KEY-----\n{}\n-----END PRIVATE KEY-----".format(self.zra_private_key)
        rsa_key = RSA.importKey(str_private_key)
        cipher = PKCS1_v1_5.new(rsa_key)
        raw_cipher_data = b64decode(message)
        return cipher.decrypt(raw_cipher_data, "", 0)

    async def private_key_application(self):
        """
        Private key application command is used to apply for private key and terminal ID from EFD system using
        registration code which is published by revenue authority.
        """
        data = {"license": self.registration_code, "sn": self.serial_number, "sw_version": self.software_version,
                "model": "IP-100",
                "manufacture": "Inspur Software Group", "imei": "",
                "os": "", "hw_sn": ""}
        self.business_data = json.dumps(data)
        self.bus_id = "R-R-01"
        self.signed_rsa_key = ""
        self.device = self.registration_code
        return await self.zra_request_data()

    async def tax_information_request(self):
        """
        This command is used to apply for tax information from EFD system by terminal ID. The tax information includes
        TPIN, tax type, tax category, tax rate,
        """
        self.bus_id = "R-R-02"
        return await self.zra_request_data()

    async def initialisation_success_request(self):
        """
        When V-EFD has been initialized successfully, the success information will be sent to EFD system.
        """
        self.bus_id = "R-R-03"
        return await self.zra_request_data()

    async def invoice_application_request(self):
        """
        This command is used for V-EFD to apply for new invoices to be issued from EFD system. The information of the
        invoice section applied will involve invoice code, Start No., End No. and the numbers of invoices in this
        section.
        """
        self.bus_id = "INVOICE-APP-R"
        return await self.zra_request_data()

    async def heart_beat_request(self):
        """
        This command is used for the EFD system to monitor the online status of V-EFD. The current device statue will
        be sent to EFD system at an interval of 60 minutes. Commands stacked in the queue list on the EFD system will be
         submitted to the V-EFD as part of the response of heartbeat monitoring command.
        """

        self.bus_id = "MONITOR-R"
        data = {"id": self.terminal_id, "lon": 0.3476, "lat": 32.5825, "sw_version": self.software_version, "batch": ""}
        self.business_data = json.dumps(data)
        return await self.zra_request_data()

    async def send_invoice(self, request_data):
        """
                This command is used for V-EFD to upload the invoice details to EFD system. If the V-EFD is online,
                the invoice data will be uploaded to EFD System immediately, otherwise the invoice data will be saved
                locally.
                """
        self.bus_id = "INVOICE-REPORT-R"

        self.business_data = json.dumps(request_data)

        return await self.zra_request_data()
