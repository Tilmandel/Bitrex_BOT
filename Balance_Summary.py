import time
from os import system
import hmac
import hashlib
import threading

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

try:
    from Crypto.Cipher import AES
except ImportError:
    encrypted = False
else:
    import getpass
    import ast
    import json

    encrypted = True
import requests

Key = "your_key"
Secret = b"your_secret_key"


def _data_return(url):
    timestamp = str(int(time.time() * 1000))
    Content = ""
    contentHash = hashlib.sha512(Content.encode()).hexdigest()
    Method = 'GET'
    PreSign = timestamp + url + Method + contentHash  # + subaccountId
    Signature = hmac.new(Secret, PreSign.encode(), hashlib.sha512).hexdigest()
    headers = {
        'Api-Key': Key,
        'Api-Timestamp': timestamp,
        'Api-Content-Hash': contentHash,
        'Api-Signature': Signature
    }
    r = requests.get(url, data={}, headers=headers, timeout=11)
    return r.json()


def feed_data(display):
    balance_all = "https://api.bittrex.com/v3/balances"
    BTC_TICKER = "https://api.bittrex.com/v3/markets/BTC-USD/ticker"
    over_all_TICKER = "https://api.bittrex.com/v3/markets/{}-BTC/ticker"
    over_all_summary = "https://api.bittrex.com/v3/markets/{}-BTC/summary"
    btc_summary = "https://api.bittrex.com/v3/markets/{}-USD/summary"
    over_all_trades = "https://api.bittrex.com/v3/markets/{}-BTC/trades"
    btc_trades = "https://api.bittrex.com/v3/markets/{}-USD/trades"
    while True:
        total = 0
        all_cur_json = _data_return(balance_all)
        BTC_price_USD = round(float(_data_return(BTC_TICKER)["bidRate"]), 2)
        for num, value in enumerate(all_cur_json):
            if float(value["total"]) != 0:
                display.curr_check[num] = value["currencySymbol"]
        for currency in all_cur_json:
            if currency["currencySymbol"] == "BTC":
                current_worth = round(BTC_price_USD * float(currency["total"]))
                change_24h = _data_return(btc_summary.format(currency["currencySymbol"]))["percentChange"]
                trades = _data_return(btc_trades.format(currency["currencySymbol"]))
                stream = len([trade_buy for trade_buy in trades if trade_buy['takerSide'] == "BUY"]) > len(
                    [trade_sell for trade_sell in trades if trade_sell['takerSide'] == "SELL"])
                total += current_worth
                display.name_worth[currency["currencySymbol"]] = current_worth
                display.name_amount[currency["currencySymbol"]] = currency['total']
                display.name_bid[currency["currencySymbol"]] = str(BTC_price_USD) + "$"
                display.name_change_24h[currency["currencySymbol"]] = change_24h
                display.stream[currency["currencySymbol"]] = stream

            if float(currency["total"]) != 0 and currency["currencySymbol"] not in ("BTC", "BTXCRD"):
                trades = _data_return(over_all_trades.format(currency["currencySymbol"]))
                stream = len([trade_buy for trade_buy in trades if trade_buy['takerSide'] == "BUY"]) > len(
                    [trade_sell for trade_sell in trades if trade_sell['takerSide'] == "SELL"])
                ask_bid = _data_return(over_all_TICKER.format(currency["currencySymbol"]))
                current_worth = round(BTC_price_USD * float(ask_bid['bidRate']) * float(currency['total']), 2)
                change_24h = _data_return(over_all_summary.format(currency["currencySymbol"]))["percentChange"]
                total += current_worth
                display.name_worth[currency["currencySymbol"]] = current_worth
                display.name_amount[currency["currencySymbol"]] = currency['total']
                display.name_bid[currency["currencySymbol"]] = ask_bid['bidRate'] + " B"
                display.name_change_24h[currency["currencySymbol"]] = change_24h
                display.stream[currency["currencySymbol"]] = stream

        display.total = total
        time.sleep(4)


class Currency(object):
    def __init__(self):
        self.curr_check = {}
        self.name_worth = {}
        self.name_amount = {}
        self.name_bid = {}
        self.name_change_24h = {}
        self.total = None
        self.stream = {}

    def __repr__(self):
        return self.total, self.name_worth, self.name_amount

    def display(self):
        while True:

            print('\33[34m' + "+++Wallet OverView+++" + '\033[0m')
            for key in sorted(self.name_worth.keys()):
                if key in self.curr_check.values():
                    amount_str = "{} Amount: {}".format(key, str(self.name_amount[key])[:6])
                    amount_str = amount_str + "{}".format(" " * (20 - len(amount_str)))
                    worth_string = " Worth: {}$".format(self.name_worth[key])
                    worth_string = worth_string + "{}".format(" " * (15 - len(worth_string)))
                    higest_bid = "Higest Bid: {}".format(self.name_bid[key])
                    higest_bid = higest_bid + "{}".format(" " * (25 - len(higest_bid)))
                    if self.stream[key]:
                        arrow = CRED_GREEN + "\u2191" + CEND
                    else:
                        arrow = CRED_RED + "\u2193" + CEND1
                    if float(self.name_change_24h[key]) >= 0:
                        change_24h = "24h change: {}".format(CRED_GREEN + self.name_change_24h[key] + "%" + CEND)
                    else:
                        change_24h = "24h change: {}".format(CRED_RED + self.name_change_24h[key] + "%" + CEND)
                    if float(self.name_worth[key]) >= 25:
                        print(CRED_GREEN + "{}|||{}|||{} ||| {}{} Stream: {}".format(amount_str, worth_string, higest_bid,
                                                                                     CEND,
                                                                                     change_24h+" "*(30-len(change_24h)), arrow))
                    else:
                        print(CRED_RED + "{}|||{}|||{} ||| {}{} Stream: {}".format(amount_str, worth_string, higest_bid,
                                                                                   CEND1,
                                                                                   change_24h+" "*(30-len(change_24h)), arrow))
            print(CRED_GREEN + "Total : {}$".format(str(self.total)[:7]) + CEND)
            time.sleep(3)
            system("cls")


if __name__ == '__main__':
    try:
        CRED_GREEN = '\033[92m'
        CEND = '\033[0m'
        CRED_RED = '\033[91m'
        CEND1 = '\033[0m'

        bittrex = Currency()
        new = threading.Thread(target=feed_data, args=(bittrex,))
        new.daemon = True
        new.start()
        time.sleep(2)
        bittrex.display()
    except BaseException as error:
        print(error)
        print('\33[41m' + "Bye" + '\033[0m')
        exit()
