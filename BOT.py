from os import system
import time
import hmac
import hashlib
import threading
import numpy
import json
import requests

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

    encrypted = True

Key = "your_key"
Secret = b"your_secret_key"


def _data_return(url, method, dt=None):
    timestamp = str(int(time.time() * 1000))
    if method in ("GET", "DELETE"):
        content = ""
        contenthash = hashlib.sha512(content.encode()).hexdigest()
        presign = timestamp + url + method + contenthash  # + subaccountId
        signature = hmac.new(Secret, presign.encode(), hashlib.sha512).hexdigest()
        headers = {
            'Api-Key': Key,
            'Api-Timestamp': timestamp,
            'Api-Content-Hash': contenthash,
            'Api-Signature': signature
        }
        if method == "GET":
            r = requests.get(url, data='', headers=headers, timeout=11)
            return r.json()
        if method == "DELETE":
            r = requests.delete(url, data='', headers=headers, timeout=11)
            return r.json()
    if method == "POST":
        content = dt
        contenthash = hashlib.sha512(bytes(json.dumps(content), "utf-8")).hexdigest()
        presign = timestamp + url + method + contenthash  # + subaccountId
        signature = hmac.new(Secret, presign.encode(), hashlib.sha512).hexdigest()
        headers = {
            'Api-Key': Key,
            'Api-Timestamp': timestamp,
            'Api-Content-Hash': contenthash,
            'Api-Signature': signature
        }
        r = requests.post(url, json=dt, headers=headers, timeout=11)
        return r.json()


class Bot(object):
    def __init__(self, crypto, profit_max, min_profit):
        self.btc_limiter = 0  # this should be open price for BTC-USD
        self.btc_drop = False  # TRUE for Pause Bot as BTC have drop FALSE to start
        self.open_transaction = {}  # append all open orders done by bot
        self.closed_transacion = []  # append all closed orders done by bot
        self.check_buy = False  # operates on True to wait False to start CHECK for BUY
        self.check_sell = False  # operates on True to wait False to start CHECK for SELL
        self.live_trades = {}  # live Trades BUY or SELL
        self.markets_summary = {}  # LOW == Lowest ASK/BID or HIGH == Highest ASK/BID
        self.live_ticker = {}  # lowest ASK highest BID
        self.wallet = {"BTC": crypto}  # Pair Crypto with Bitcoin for profit : TUPLE, LIST
        self.profit_max = profit_max  # limiter for profit celling
        self.min_profit = min_profit  # limiter for profit flooring
        self.curr_price_for_profit_max = {}  # currency price for max profit
        self.curr_price_for_profit_min = {}  # currency price for min profit
        self.last_order_price = {}  # Last order currency price float Currency_Symbol : price ;dict
        self.last_order_amount = {}  # Last order currency amount float Currency_Symbol : amount ;dict
        self.last_order_btc_price = {}  # Last order BTC price for provided crypto from .json file
        self.total_cost = 0  # total cost of all paired crypto
        self.total_current = 0  # total current state of crypto worth with corelation to BTC price
        self.total_profit_max = 0  # total MAX profit for whole pair
        self.total_profit_min = 0  # total MIN profit for whole pair
        self.stream = {}  # this shows is price will raise or fall LIST with [bool,inc count,drp count]
        self.data_loop = False  # switcher for data loop also thread is daemon will should die after exit

    def drop_open_transaction(self):  # Drop open transaction for json file when emergency occur
        with open("path_for_opentransaction_drop", "a") as file:
            json.dump(self.open_transaction, file)

    def get_request_data(self):  # spawned in new thr for live data, 3 Request for each crypto with limit 60req per/min
        while self.data_loop:
            total = 0
            max = 0
            min = 0
            for currency in self.wallet["BTC"]:
                markets_ticker_btc = "https://api.bittrex.com/v3/markets/{}-USD/ticker".format("BTC")
                markets_trades = "https://api.bittrex.com/v3/markets/{}-BTC/trades".format(currency)
                markets_ticker = "https://api.bittrex.com/v3/markets/{}-BTC/ticker".format(currency)
                markets_summary = "https://api.bittrex.com/v3/markets/{}-BTC/summary".format(currency)
                url_orders = "https://api.bittrex.com/v3/orders/closed"
                closed_orders = _data_return(url_orders, "GET")
                btc_ticker = _data_return(markets_ticker_btc, "GET")['bidRate']  # Current price for BTC
                data_returned_trades = _data_return(markets_trades.format(currency), "GET")  # All open trades returned
                data_returned_ticker = _data_return(markets_ticker.format(currency),
                                                    "GET")  # current BID(low) and ASK(high)
                data_returned_markets_summary = _data_return(markets_summary.format(currency),
                                                             "GET")  # All orders returned
                self.live_trades[currency] = data_returned_trades
                self.live_ticker[currency] = data_returned_ticker
                self.markets_summary[currency] = data_returned_markets_summary
                self.btc_limiter = float(btc_ticker)
                key_last_order = None
                last_order = {key: val for key, val in enumerate(closed_orders)
                              if val["status"] == "CLOSED" and val["marketSymbol"] == "{}-BTC".format(currency)}
                for key_order in last_order:
                    if last_order[key_order]["status"] == "CLOSED" \
                            and last_order[key_order]["marketSymbol"] == "{}-BTC".format(currency):
                        key_last_order = key_order
                        break

                last_order_price = float(last_order[key_last_order]["limit"])
                last_order_amount = float(last_order[key_last_order]['quantity'])

                cost_of_transaction = float(self.last_order_btc_price[currency]) * last_order_price * last_order_amount
                profit = cost_of_transaction + (self.profit_max / float(len(self.wallet['BTC'])))
                profit_min = cost_of_transaction + (self.min_profit / float(len(self.wallet["BTC"])))
                price_for_profit = profit / last_order_amount / self.btc_limiter
                price_for_min_profit = profit_min / last_order_amount / self.btc_limiter
                self.curr_price_for_profit_max[currency] = price_for_profit
                self.curr_price_for_profit_min[currency] = price_for_min_profit
                self.last_order_price[currency] = last_order_price
                self.last_order_amount[currency] = last_order_amount
                total += cost_of_transaction
                max += profit
                min += profit_min
            self.total_cost = total
            self.total_profit_max = max
            self.total_profit_min = min

            time.sleep(15)

    @staticmethod
    def post_request_data(crypto, direction, qty, limit):  # BUY or SELL order will be send depend on analyse
        url = "https://api.bittrex.com/v3/orders"
        if crypto != "BTC":
            data = {
                "marketSymbol": "{}-BTC".format(crypto),
                "direction": direction,
                "type": "LIMIT",
                "quantity": qty,
                "limit": limit,
                "timeInForce": "GOOD_TIL_CANCELLED"
            }
        if crypto == "BTC":
            data = {
                "marketSymbol": "{}-USD".format(crypto),
                "direction": direction,
                "type": "LIMIT",
                "quantity": qty,
                "limit": limit,
                "timeInForce": "GOOD_TIL_CANCELLED"
            }

        post_order = _data_return(url, "POST", data)
        bot.open_transaction[crypto] = [post_order]
        bot.open_transaction[crypto].append({"BTC": bot.btc_limiter})
        bot.drop_open_transaction()


    def read_last_trans_price_btc(self):
        with open(r"PATH_FOR_JASON_FILE") as file:
            price_for_last_trans_btc = json.load(file)
        for currency in self.wallet['BTC']:
            self.last_order_btc_price[currency] = price_for_last_trans_btc[0][currency]

    def analyse(self):
        step = 0.00000001
        total_current = 0
        for currency in self.wallet["BTC"]:
            high = float(self.markets_summary[currency]['high'])
            low = float(self.markets_summary[currency]['low'])
            trades_price = {round(float(trade["rate"]), 8) for trade in self.live_trades[currency]}
            raise_price = {round(x, 8) for x in numpy.arange(float(self.live_ticker[currency]["bidRate"]),
                                                             float(self.live_ticker[currency]["bidRate"]) + high - low,
                                                             step)}
            drop_price = {round(x, 8) for x in numpy.arange(float(self.live_ticker[currency]["bidRate"]) - high - low,
                                                            float(self.live_ticker[currency]["bidRate"]), step)}
            inc = len(raise_price.intersection(trades_price))
            drp = len(drop_price.intersection(trades_price))
            stream_direct = inc > drp

            self.stream[currency] = [stream_direct, inc, drp]
            total_current += float(self.live_ticker[currency]['bidRate']) * self.last_order_amount[
                currency] * self.btc_limiter
            self.total_current = total_current
            if (self.stream[currency][1] > self.stream[currency][0] and self.total_current >= int(
                    self.total_profit_max)) or (
                    self.stream[currency][1] < self.stream[currency][0] and self.total_current >= int(
                self.total_profit_min)):
                btc_qty_to_sell = 0

                btc_qty_to_sell += float(self.live_ticker[currency]["bidRate"]) * float(
                    self.last_order_amount[currency])
                bot.post_request_data(currency, "SELL", self.last_order_amount[currency],
                                      self.live_ticker[currency]["bidRate"])
                bot.post_request_data("BTC", "SELL", btc_qty_to_sell, self.btc_limiter)

    def display(self):
        cred_green = '\033[92m'
        cend = '\033[0m'
        cred_red = '\033[91m'
        system("cls")
        if self.check_sell:
            # print(len(self.price_raise),len(self.price_drop))
            worth = "Currency: {}: {:.2f}$".format("BTC", self.btc_limiter)
            worth = worth + " " * (10 - len(worth))
            print(cred_green + worth)
            for currency in self.wallet['BTC']:
                worth = "Currency: {}: {:.2f}$".format(currency,
                                                       float(self.live_ticker[currency]["bidRate"]) *
                                                       self.last_order_amount[
                                                           currency] * self.btc_limiter)
                worth = worth + " " * (10 - len(worth))
                print(worth)
            print("Total Cost: {:.2f}$ ".format(self.total_cost))
            if self.total_cost > self.total_current:
                print(cred_red + "Total Current: {:.2f}$ ".format(self.total_current))
            else:
                print("Total Current: {:.2f}$ ".format(self.total_current))
            print(cred_green + "Total MAX profit: {:.2f}$ ".format(self.total_profit_max))
            print("Total MIN profit: {:.2f}$ ".format(self.total_profit_min) + cend)

    @staticmethod
    def main(obj):
        try:
            setattr(obj, "data_loop", True)
            pull_in_data_thread = threading.Thread(target=obj.get_request_data)
            pull_in_data_thread.daemon = True
            pull_in_data_thread.start()
            obj.read_last_trans_price_btc()
            time.sleep(7)
            while True:
                obj.analyse()
                obj.display()
                time.sleep(1)
        except Exception as error:
            print(error)
            obj.drop_open_transaction()


if __name__ == '__main__':

    bot = Bot(["DOGE", "GAME"], 3.5, 2)
    setattr(bot, "check_sell", True)
    bot.main(bot)
