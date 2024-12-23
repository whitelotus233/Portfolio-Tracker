import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime

# Connect to SQLite database (or create it if it doesn't exist)
def connect_db():
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    # Create investments table if it doesn't already exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS investments (
            name TEXT PRIMARY KEY,
            quantity REAL,
            avg_buy_price REAL,
            profit_loss_pct REAL DEFAULT 0
        )
    ''')
    # Create transactions table if it doesn't already exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            transaction_type TEXT,
            quantity REAL,
            price REAL,
            timestamp TEXT
        )
    ''')

    conn.commit()
    return conn, cursor

conn, cursor = connect_db()

# Function to fetch investment names from the database for the dropdown
def get_investment_names():
    cursor.execute("SELECT name FROM investments")
    return [row[0] for row in cursor.fetchall()]

# Function to fetch and display data in the table
def refresh_table():
    # Clear current rows in the Treeview
    for row in portfolio_table.get_children():
        portfolio_table.delete(row)

    # Fetch all investments from the database
    cursor.execute("SELECT * FROM investments")
    investments = cursor.fetchall()

    total_investment = 0
    total_profit_loss = 0

    # Insert each investment as a row in the table
    for i, (name, quantity, avg_buy_price, profit_loss_pct) in enumerate(investments, start=1):
        amount_invested = quantity * avg_buy_price

        # Calculate profit/loss based on transaction history
        cursor.execute("SELECT transaction_type, quantity, price FROM transactions WHERE name = ?", (name,))
        transactions = cursor.fetchall()
        total_profit_loss_investment = 0
        last_sell_price = "-"

        for transaction_type, trans_quantity, trans_price in transactions:
            if transaction_type == "Sell":
                total_profit_loss_investment += trans_quantity * (trans_price - avg_buy_price)
                last_sell_price = trans_price

        profit_loss_pct = (total_profit_loss_investment / amount_invested * 100) if amount_invested > 0 else 0

        # Update profit_loss_pct in the database
        cursor.execute("UPDATE investments SET profit_loss_pct = ? WHERE name = ?", (profit_loss_pct, name))

        total_investment += amount_invested
        total_profit_loss += total_profit_loss_investment

        portfolio_table.insert('', 'end', values=(i, name, quantity, avg_buy_price, amount_invested, last_sell_price, total_profit_loss_investment, f"{profit_loss_pct:.2f}%", "Sell", "Delete"))

    conn.commit()

    total_investment_value.config(text=f"{total_investment:.2f}")
    total_profit_loss_value.config(text=f"{total_profit_loss:.2f}")
    total_profit_loss_pct_value.config(text=f"{(total_profit_loss / total_investment * 100 if total_investment > 0 else 0):.2f}%")

    refresh_dropdown()

# Function to update dropdown values
def refresh_dropdown():
    name_entry['values'] = get_investment_names()

# Function to add or update investment
def add_investment():
    name = name_entry.get()
    try:
        quantity = float(quantity_entry.get())
        buy_price = float(buy_price_entry.get())
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter valid numbers for quantity and buy price.")
        return

    try:
        # Check if investment exists in DB
        cursor.execute("SELECT quantity, avg_buy_price FROM investments WHERE name = ?", (name,))
        result = cursor.fetchone()

        if result:
            total_quantity = result[0] + quantity
            avg_buy_price = ((result[0] * result[1]) + (quantity * buy_price)) / total_quantity
            cursor.execute("UPDATE investments SET quantity = ?, avg_buy_price = ? WHERE name = ?", (total_quantity, avg_buy_price, name))
        else:
            cursor.execute("INSERT INTO investments (name, quantity, avg_buy_price) VALUES (?, ?, ?)", (name, quantity, buy_price))

        # Log the transaction
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO transactions (name, transaction_type, quantity, price, timestamp) VALUES (?, ?, ?, ?, ?)", 
                       (name, "Buy", quantity, buy_price, timestamp))

        conn.commit()
        refresh_table()
        
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"An error occurred: {e}")

# Function to sell investment
def sell_investment_popup():
    selected_item = portfolio_table.selection()
    if not selected_item:
        messagebox.showwarning("No Selection", "Please select an investment to sell.")
        return

    investment_name = portfolio_table.item(selected_item)['values'][1]
    current_quantity = portfolio_table.item(selected_item)['values'][2]

    popup = tk.Toplevel(app)
    popup.title("Sell Investment")
    popup.geometry("300x200")

    tk.Label(popup, text=f"Selling: {investment_name}").pack(pady=5)
    tk.Label(popup, text=f"Available Quantity: {current_quantity}").pack(pady=5)

    tk.Label(popup, text="Quantity to Sell:").pack(pady=5)
    quantity_entry = tk.Entry(popup)
    quantity_entry.pack(pady=5)

    tk.Label(popup, text="Sell Price:").pack(pady=5)
    sell_price_entry = tk.Entry(popup)
    sell_price_entry.pack(pady=5)

    def confirm_sell():
        try:
            quantity_to_sell = float(quantity_entry.get())
            sell_price = float(sell_price_entry.get())

            cursor.execute("SELECT quantity, avg_buy_price FROM investments WHERE name = ?", (investment_name,))
            result = cursor.fetchone()

            if result and result[0] >= quantity_to_sell:
                new_quantity = result[0] - quantity_to_sell

                cursor.execute("UPDATE investments SET quantity = ? WHERE name = ?", (new_quantity, investment_name))

                # Log the transaction
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO transactions (name, transaction_type, quantity, price, timestamp) VALUES (?, ?, ?, ?, ?)", 
                               (investment_name, "Sell", quantity_to_sell, sell_price, timestamp))

                conn.commit()

                total_received = quantity_to_sell * sell_price
                cost_basis = quantity_to_sell * result[1]
                profit_loss = total_received - cost_basis

                messagebox.showinfo("Sell Successful", f"Sold {quantity_to_sell} of {investment_name} for {total_received:.2f}.\nProfit/Loss: {profit_loss:.2f}")
                refresh_table()
                popup.destroy()
            else:
                messagebox.showwarning("Sell Failed", "Not enough quantity to sell or investment not found.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for quantity and sell price.")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}")

    tk.Button(popup, text="Confirm Sell", command=confirm_sell).pack(pady=10)

# Function to delete investment
def delete_investment():
    selected_item = portfolio_table.selection()
    if not selected_item:
        messagebox.showwarning("No Selection", "Please select an investment to delete.")
        return

    investment_name = portfolio_table.item(selected_item)['values'][1]
    try:
        cursor.execute("DELETE FROM investments WHERE name = ?", (investment_name,))
        conn.commit()
        refresh_table()
        messagebox.showinfo("Success", f"Investment '{investment_name}' deleted successfully.")
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"An error occurred: {e}")

# Create the main application window
app = tk.Tk()
app.title("Portfolio Tracker")
app.geometry("1600x1200")
app.state("zoomed")

# Set style to center-align text in the Treeview headings
style = ttk.Style(app)
style.configure("Treeview.Heading", anchor="center")

# Create frames for layout
top_frame = tk.Frame(app)
top_frame.pack(side="top", fill="x", padx=20, pady=20)

bottom_frame = tk.Frame(app)
bottom_frame.pack(side="top", fill="both", expand=True)

# Summary section
summary_frame = tk.LabelFrame(top_frame, text="Portfolio Summary", font=("Arial", 16, "bold"), padx=10, pady=10, labelanchor="n")
summary_frame.pack(side="left", anchor="nw", padx=20, pady=10)

total_investment_label = tk.Label(summary_frame, text="Total Investment: ", font=("Arial", 14, "bold"))
total_investment_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
total_investment_value = tk.Label(summary_frame, text="0.00", font=("Arial", 14))
total_investment_value.grid(row=0, column=1, sticky="e", padx=5, pady=5)

total_profit_loss_label = tk.Label(summary_frame, text="Total Profit/Loss: ", font=("Arial", 14, "bold"))
total_profit_loss_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
total_profit_loss_value = tk.Label(summary_frame, text="0.00", font=("Arial", 14))
total_profit_loss_value.grid(row=1, column=1, sticky="e", padx=5, pady=5)

total_profit_loss_pct_label = tk.Label(summary_frame, text="Total Profit/Loss (%): ", font=("Arial", 14, "bold"))
total_profit_loss_pct_value = tk.Label(summary_frame, text="0.00%", font=("Arial", 14))
total_profit_loss_pct_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
total_profit_loss_pct_value.grid(row=2, column=1, sticky="e", padx=5, pady=5)

# Center-aligned data entry fields
entry_frame = tk.Frame(top_frame)
entry_frame.pack(side="top", pady=10)

name_label = tk.Label(entry_frame, text="Investment Name:")
name_label.grid(row=0, column=0, padx=5, pady=5)
name_entry = ttk.Combobox(entry_frame, values=get_investment_names(), width=30)
name_entry.grid(row=0, column=1, padx=5, pady=5)

quantity_label = tk.Label(entry_frame, text="Quantity:")
quantity_label.grid(row=1, column=0, padx=5, pady=5)
quantity_entry = tk.Entry(entry_frame, width=30)
quantity_entry.grid(row=1, column=1, padx=5, pady=5)

buy_price_label = tk.Label(entry_frame, text="Buy Price:")
buy_price_label.grid(row=2, column=0, padx=5, pady=5)
buy_price_entry = tk.Entry(entry_frame, width=30)
buy_price_entry.grid(row=2, column=1, padx=5, pady=5)

# Button to add investment
add_button = tk.Button(entry_frame, text="Add Investment", command=add_investment)
add_button.grid(row=3, column=0, columnspan=2, pady=10)

# Treeview widget for the portfolio table
portfolio_table = ttk.Treeview(bottom_frame, columns=("serial", "name", "quantity", "buy_price", "amount", "sell_price", "profit_loss", "profit_loss_pct", "sell", "delete"), show="headings", height=20)
portfolio_table.pack(fill="both", expand=True)

portfolio_table.heading("serial", text="S.No")
portfolio_table.heading("name", text="Investment Name")
portfolio_table.heading("quantity", text="Quantity")
portfolio_table.heading("buy_price", text="Buy Price")
portfolio_table.heading("amount", text="Amount Invested")
portfolio_table.heading("sell_price", text="Sell Price")
portfolio_table.heading("profit_loss", text="Profit/Loss")
portfolio_table.heading("profit_loss_pct", text="Profit/Loss (%)")
portfolio_table.heading("sell", text="Sell")
portfolio_table.heading("delete", text="Delete")

portfolio_table.column("serial", width=50, anchor="center")
portfolio_table.column("name", width=200, anchor="center")
portfolio_table.column("quantity", width=100, anchor="center")
portfolio_table.column("buy_price", width=100, anchor="center")
portfolio_table.column("amount", width=120, anchor="center")
portfolio_table.column("sell_price", width=100, anchor="center")
portfolio_table.column("profit_loss", width=100, anchor="center")
portfolio_table.column("profit_loss_pct", width=120, anchor="center")
portfolio_table.column("sell", width=50, anchor="center")
portfolio_table.column("delete", width=50, anchor="center")

# Function to handle table clicks
def handle_table_click(event):
    selected_item = portfolio_table.selection()
    if not selected_item:
        return

    column_id = portfolio_table.identify_column(event.x)

    if column_id == "#9":  # Sell column
        sell_investment_popup()
    elif column_id == "#10":  # Delete column
        delete_investment()

portfolio_table.bind("<ButtonRelease-1>", handle_table_click)

# Refresh the table initially
refresh_table()

# Start the application
app.mainloop()

# Close the database connection on exit
conn.close()
