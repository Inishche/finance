import os
import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT symbol, price, name, SUM(shares) as shares FROM finance_two WHERE id = ? GROUP BY symbol", session["user_id"])

    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = round((user_cash[0]["cash"]), 2)

    total_cash = cash
    for stock in stocks:
        total_cash += stock["price"] * stock["shares"]
        total_cash = round(total_cash, 2)
    #total_cash = usd(total_cash)

    return render_template("index.html", data=stocks, cash=usd(cash), total_cash=usd(total_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    if request.method == "POST":
        if not request.form.get("symbol") or not lookup(request.form.get("symbol")):
            return apology("must provide symbol", 400)
        if not request.form.get("shares"):
            return apology("must provide shares", 400)
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide integer", 400)
        if shares <= 0:
            return apology("must provide shares more than 0", 400)
        price = lookup(request.form.get("symbol"))["price"]

        cash = float(db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])[0]["cash"])

        sum = price*shares
        if sum > cash:
            return apology("You don`t have money for this operation", 403)
        # update user`s cash
        cash_now = cash - sum
        db.execute("UPDATE users SET cash=:cash_now WHERE id=:user_id", cash_now=cash_now, user_id=session["user_id"])

        # username = db.execute("SELECT username FROM users WHERE id = :user_id", user_id = session.get("user_id"))
        # CREATE NEW TABLE
        date = datetime.datetime.now()
        name=lookup(request.form.get("symbol"))["name"]
        db.execute("INSERT INTO finance_two (id, symbol, price, date, shares, name, trans) VALUES (:id, :symbol, :price, :date, :shares, :name, :trans)", id=session["user_id"], symbol=request.form.get("symbol"), price=price, date=date, shares=shares, name=name, trans="BOUGHT")

        flash("Bought!")
    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    hist = db.execute("SELECT id, symbol, price, date, shares, name, trans FROM finance_two WHERE id = ?", session["user_id"])
    return render_template("history.html", hist=hist)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    if request.method == "POST":
        if not lookup(request.form.get("symbol")) or lookup(request.form.get("symbol")) == None:
            return apology("must provide symbol", 400)
        #flash("You are registered!")
        return render_template("iquote.html", symbol=lookup(request.form.get("symbol")))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide confirm password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password not equal confirm_password")
            # Hash the user password
        hash = generate_password_hash(request.form.get('password'))

        # insert password in users
        try:
            row = db.execute("INSERT INTO users(username, hash) VALUES (?, ?)", request.form.get("username"), hash)
            # Redirect user to home page
        except:
            return apology("user name isn`t free", 400)
        session["user_id"] = row
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    #for get method
    if request.method == "GET":
        symbols = db.execute("SELECT symbol FROM finance_two WHERE id = ? GROUP BY symbol", session["user_id"])
        return render_template("sell.html", symbols=symbols)
    #for post method
    if request.method == "POST":
        if not request.form.get("symbol") or not lookup(request.form.get("symbol")):
            return apology("must provide symbol", 403)
        if not request.form.get("shares"):
             return apology("must provide shares", 403)

        #how many shares input to sell
        shares = int(request.form.get("shares"))
        if shares <= 0:
             return apology("must provide shares more than 0", 403)
        # user`s shares
        shares_db = db.execute("SELECT shares FROM finance_two WHERE id = ? AND symbol = ? Group BY symbol", session["user_id"], (request.form.get("symbol")))[0]["shares"]

        # check amount shares
        if shares_db < shares:
            return apology("You don`t have enough shares", 403)

        price = (lookup(request.form.get("symbol"))["price"]) * shares
        # update cash and db
        cash_now = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        date = datetime.datetime.now()
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_now + price, session["user_id"])
        db.execute("INSERT into finance_two (id, symbol, price, date, shares, name, trans) VALUES (:id, :symbol, :price, :date, :shares, :name, :trans)", id=session["user_id"], symbol=request.form.get("symbol"), price=price, date=date, shares=-shares, name=lookup(request.form.get("symbol"))["name"], trans="SOLD")
        flash("Sold!")
        return redirect("/")

