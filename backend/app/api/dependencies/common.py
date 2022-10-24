def clean_currency(currency):
    if currency == 'UGX' or currency == '101':
        return 'UGX'
    elif currency == 'USD' or currency == '102':
        return 'USD'
    elif currency == 'EUR' or currency == '104':
        return 'EUR'


def clean_currency_product(currency):
    if currency in ('UGX', '101'):
        return '101'
    elif currency in ('USD', '102'):
        return '102'
    elif currency in ('EUR', '104'):
        return '104'


def clean_buyer_type(buyer_type):
    if buyer_type.upper() in ('27', 'B2B', 'B2G'):
        return "0"
    elif buyer_type.upper() in ('28', 'B2F'):
        return "2"
    else:
        return "1"


def get_tax_rate(tax_rule):
    if tax_rule.upper() == 'VAT':
        return True

    return False


def change_keys(obj, convert):
    """
    Recursively goes through the dictionary obj and replaces keys with the convert function.
    """
    if isinstance(obj, (str, int, float)):
        return obj
    if isinstance(obj, dict):
        new = obj.__class__()
        for k, v in obj.items():
            new[convert(k)] = change_keys(v, convert)
    elif isinstance(obj, (list, set, tuple)):
        new = obj.__class__(change_keys(v, convert) for v in obj)
    else:
        return obj
    return new


def convert(k):
    return k.replace('-', '_')