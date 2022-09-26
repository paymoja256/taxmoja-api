import structlog as structlog
import json
import os

from fastapi import Header, HTTPException
from starlette.status import HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR
from app.api.services.tax import TaxService
from app.db.schemas.core import ClientAuthenticationBase
from app.core.config import SETTINGS_FILE

struct_logger = structlog.get_logger(__name__)


def get_configuration_settings():
    file = os.path.realpath(SETTINGS_FILE)

    struct_logger.error(event="get_configuration_settings", settings_path="{}".format(file))

    if not file:
        struct_logger.error(event="get_configuration_settings", error="settings file has not been found")
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="settings file has not been file. "
                                                                               "Service can not continue, "
                                                                               "please see settings template")

    with open(file) as fin:
        struct_logger.info(event="get_configuration_settings", msg="settings file has been found")
        print(fin)
        return json.load(fin)


def get_tax_service(x_tax_id: str = Header(...), x_api_key_header: str = Header(...), x_tax_country_code=Header(...)):
    return create_service_from_settings(x_api_key_header, x_tax_id, x_tax_country_code)


def get_url_tax_service(x_tax_id, x_tax_country_code, x_api_key_header):
    return create_service_from_settings(x_api_key_header, x_tax_id, x_tax_country_code)


def create_service_from_settings(x_api_key_header, x_tax_id, x_tax_country_code):
    try:
        api_settings = get_configuration_settings()

        struct_logger.info(event="get_tax_service",
                           message="validating api settings"
                           )

        client_settings = api_settings[x_tax_country_code][x_tax_id]

        api_keys = api_settings[x_tax_country_code][x_tax_id]["api_keys"]

        security_validation = x_api_key_header == api_keys["production"]

        if client_settings["testing"]:
            security_validation = x_api_key_header == api_keys["staging"]

        if not client_settings or not security_validation:
            struct_logger.error(event="get_tax_service",
                                error="No settings configured for {} ".format(x_tax_id),
                                security_validation=security_validation,
                                )
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Tax Details header is invalid")

        interface_details = ClientAuthenticationBase(
            **{"tax_country_code": x_tax_country_code.upper(), "x_api_key_header": x_api_key_header,
               "tax_id": x_tax_id})

        struct_logger.info(event="get_tax_service",
                           message="settings found for {} in {}".format(x_tax_id, x_tax_country_code)
                           )

        return TaxService(interface_details, client_settings)

    except Exception as ex:
        struct_logger.error(event="get_tax_service",
                            error=ex
                            )

        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Error processing login details {}".format(str(ex)))
