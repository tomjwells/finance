import numpy as np
from typing import Literal
from datetime import datetime
from modules.derivatives.monte_carlo import monte_carlo
from modules.derivatives.black_scholes import black_scholes_option
from modules.derivatives.binomial_model import EUPrice, USPrice
from modules.markowitz.main import main
from flask import Flask, request, jsonify, make_response
import pandas as pd
from typing import List
import random
import time
import json
import gzip
import os
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
# from sqlalchemy import create_engine
import libsql_experimental as libsql
# import libsql_client as libsql


# import redis
# import functools
# import pickle

# r = redis.Redis.from_url(url=os.getenv("REDIS_URL").replace("redis://", "rediss://"))

# Decorator to cache the result of a function using Redis


# def cache(func):
#   @functools.wraps(func)
#   def wrapper(*args, **kwargs):
#     key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
#     if (val := r.get(key)) is not None:
#       print("Cache hit!")
#       return pickle.loads(val)
#     else:
#       print("Cache miss!")
#       val = func(*args, **kwargs)
#       r.set(key, pickle.dumps(val))
#       return val
#   return wrapper


app = Flask(__name__)

# con = libsql.create_client_sync(f"{os.getenv('TURSO_DATABASE_URL')}/?authToken={os.getenv('TURSO_AUTH_TOKEN')}")
# con = libsql.connect(database=os.getenv('TURSO_DATABASE_URL'), auth_token=os.getenv("TURSO_AUTH_TOKEN"))
# con = create_engine(f"sqlite+{os.getenv('TURSO_DATABASE_URL')}/?authToken={os.getenv('TURSO_AUTH_TOKEN')}&secure=true", connect_args={'check_same_thread': False, "timeout": 10*60}, echo=True)

# Markowitz


@app.route("/api/markowitz/main")
def markowitz_main():
  assets: List[str] = request.args.getlist('assets')
  startYear: int = int(request.args.get('startYear'))
  endYear: int = int(request.args.get('endYear'))
  r: float = float(request.args.get('r'))
  allowShortSelling: bool = request.args.get('allowShortSelling') == 'true'

  assert isinstance(assets, list), "assets should be a list"
  assert isinstance(startYear, int), "startYear should be a int"
  assert isinstance(endYear, int), "endYear should be a int"
  assert isinstance(allowShortSelling,
                    bool), "allowShortSelling should be a bool"

  start_date = f'{startYear}-01-01'
  end_date = datetime.now().strftime(
      '%Y-%m-%d') if endYear == datetime.now().year else f'{endYear}-01-01'

  columns_str = ', '.join([f'"{asset}"' for asset in assets if asset.isidentifier()])
  con = libsql.connect(database=os.getenv('TURSO_DATABASE_URL'), auth_token=os.getenv("TURSO_AUTH_TOKEN"))
  results = con.execute(f"SELECT Date, {columns_str} FROM price_history WHERE date BETWEEN ? AND ?", (start_date, end_date)).fetchall()
  rets = pd.DataFrame(results, columns=["Date"] + assets).set_index('Date').pct_change().iloc[1:]
  # SQLAlchemy takes the function size beyond AWS 250MB limit, so I have to build DataFrames more manually for now.
  # rets = pd.read_sql(f"SELECT Date, {columns_str} FROM price_history WHERE date BETWEEN ? AND ?", con,
  #                    params=(start_date, end_date), index_col='Date', parse_dates=["Date"]).pct_change().iloc[1:]
  result = main(assets, rets, allowShortSelling, R_f=r)

  # Compress the response to enable larger payload
  content = gzip.compress(json.dumps(result).encode('utf8'), 5)
  response = make_response(content)
  response.headers['Content-length'] = str(len(content))
  response.headers['Content-Encoding'] = 'gzip'
  return response


@app.route("/api/seed_db")
def seed_db():
  if app.debug == True:
    import yfinance as yf
    risk_free_rate = yf.download("^IRX", progress=False,)[
        'Adj Close'].tail(1)/100
    risk_free_rate.to_sql(name='risk_free_rate',
                          con=con, if_exists='replace')
    price_history = download_symbols(pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol'].to_list())
    returns_history = price_history.pct_change().dropna()
    price_history.to_sql(name='price_history', con=con,
                         if_exists='replace', chunksize=500)
    # May need to adjust chunksize, or con timeout
    returns_history.to_sql(name='returns_history',
                           con=con, if_exists='replace', chunksize=500)

    return jsonify({"message": "Database seeded successfully"})
  else:
    return jsonify({"error": "Cannot seed database in production"}), 400


# @cache
def download_symbols(symbols: List[str]) -> pd.DataFrame:
  """
    Downloads the adjusted close prices for the tickers in parallel
  """

  # Download data in parallel
  with ThreadPoolExecutor() as executor:
    results = executor.map(lambda ticker: get_returns(ticker), symbols)

  # Create a DataFrame from the results
  return pd.concat(list(results), axis=1, keys=symbols)


# @cache
def get_returns(ticker: str) -> pd.Series:
  # yfinance.download frequently errors, this wrapper makes downloading reliable
  for _ in range(int(1e5)):
    with ThreadPoolExecutor() as executor:
      future = executor.submit(download_data, ticker)
      try:
        price_data = future.result(timeout=2)  # Timeout after 2 seconds
        if price_data is not None:
          return price_data['Adj Close']
      except TimeoutError:
        print("yfinance request timed out. Retrying...")
      except Exception as e:
        print(f"An error occurred: {e}. Retrying...")
      time.sleep(2)


# @cache
def download_data(ticker: str) -> pd.Series:
  """
    Downloads the adjusted close prices for a given ticker and calculates the daily returns
  """
  import yfinance as yf
  return yf.download(ticker.replace('.', '-'), progress=False)


# Derivatives


# Route for option-price

@app.route("/api/derivatives/option-price")
def get_option_price():
  option_type = request.args.get('optionType')
  assert option_type in [
      'european', 'american'], "option_type should be either 'european' or 'american'"
  method = request.args.get('method')
  assert method in ['binomial', 'black-scholes',
                    'monte-carlo'], "method should be either 'binomial', 'black-scholes', 'monte-carlo'"
  instrument: Literal['call', 'put'] = request.args.get('instrument')
  assert instrument in [
      'call', 'put'], "instrument should be either 'call' or 'put'"

  t: datetime = datetime.now()
  T: datetime = datetime.strptime(request.args.get('T'), '%Y-%m-%d')
  if t > T:
    return jsonify({"error": f"t: {t} should be less than T: {T}"}), 400
  tau = (T - t).days / 365
  K: float = float(request.args.get('K'))
  assert isinstance(K, (float)), "K should be a float"
  ticker = request.args.get('ticker') if request.args.get('ticker').isidentifier() else None
  assert isinstance(ticker, str), "ticker should be a string"
  R_f: float = float(request.args.get('R_f'))

  con = libsql.connect(database=os.getenv('TURSO_DATABASE_URL'), auth_token=os.getenv("TURSO_AUTH_TOKEN"))
  results = con.execute(f'SELECT Date, "{ticker}" FROM price_history').fetchall()
  price_history = pd.DataFrame(results, columns=["Date", ticker]).set_index('Date')
  # price_history = pd.read_sql(f"SELECT Date, {ticker} FROM price_history", con, index_col='Date', parse_dates=["Date"])
  S_0 = round(price_history.tail(1)[ticker].iloc[0], 2)
  returns = price_history.pct_change()
  sigma = np.sqrt(365) * returns.std().iloc[0]

  print("S_0: ", S_0, "sigma: ", sigma, "R_f: ", R_f, "K: ", K, "tau: ", tau,
        "method: ", method, "option_type: ", option_type, "instrument: ", instrument)

  if method == 'binomial':
    num_steps = int(1e3)
    if option_type == 'european':
      return jsonify(EUPrice(instrument, S_0, sigma, R_f, K, tau, num_steps))
    elif option_type == 'american':
      return jsonify(USPrice(instrument, S_0, sigma, R_f, K, tau, num_steps))

  if method == 'black-scholes':
    if option_type == 'european':
      bs = black_scholes_option(S_0, K, tau, R_f, sigma)
      return jsonify(bs.value(instrument))
    if option_type == 'american':
      return jsonify({"error": "American options are not supported"})

  if method == 'monte-carlo':
    num_trials = int(1e5)
    num_timesteps = 100
    if option_type == 'european':
      return jsonify(monte_carlo(instrument, S_0, K, tau, R_f, sigma, num_trials=num_trials, num_timesteps=num_timesteps, seed=random.randint(0, int(1e6))))
    elif option_type == 'american':
      return jsonify({"error": "American options are not supported"})
