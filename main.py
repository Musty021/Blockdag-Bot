try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
except ImportError:
    print("Installing telegram library...")
    import subprocess
    subprocess.run(["pip", "install", "python-telegram-bot"], check=True)
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from web3 import Web3
import requests
import qrcode
from PIL import Image
import io
import uuid
import threading
from flask import Flask, request, jsonify, send_file
import os

# Your bot token
BOT_TOKEN = "8361038742:AAFE3wPyw0FZ-7QPLW8fetPYBAE19ZSLrjQ"

# RPC endpoint (replace with official BlockDAG RPC when available)
BLOCKDAG_RPC = "https://rpc.blockdag.network"
w3 = Web3(Web3.HTTPProvider(BLOCKDAG_RPC))

# BlockDAG Explorer API (replace with real one once available)
EXPLORER_API = "https://explorer.blockdag.network/api?module=account&action=txlist&address={}"

# Store user wallets and sessions
user_wallets = {}
wallet_sessions = {}  # session_id -> {'user_id': int, 'wallet_address': str, 'status': str}

# Current BlockDAG price and info
BDAG_PRESALE_PRICE = 0.0016  # $0.0016 per BDAG
MIN_PURCHASE_USD = 15  # Minimum $15 purchase

# Flask app for MetaMask integration
app = Flask(__name__)

# Get domain for the web interface
def get_domain():
    domain = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
    if not domain.startswith('http'):
        domain = f'https://{domain}'
    return domain

@app.route('/connect-wallet/<session_id>')
def connect_wallet_page(session_id):
    """Serve the MetaMask connection page"""
    try:
        with open('metamask_web.html', 'r') as f:
            html = f.read()
        # Inject session ID into the page
        html = html.replace('urlParams.get(\'session\')', f'"{session_id}"')
        return html
    except Exception as e:
        return f"Error loading page: {str(e)}", 500

@app.route('/api/wallet-connected', methods=['POST'])
def wallet_connected():
    """Handle wallet connection from web interface"""
    try:
        data = request.json
        session_id = data.get('session_id')
        wallet_address = data.get('wallet_address')
        chain_id = data.get('chain_id')

        if session_id in wallet_sessions:
            session = wallet_sessions[session_id]
            session['wallet_address'] = wallet_address
            session['chain_id'] = chain_id
            session['status'] = 'connected'

            # Store in user wallets
            user_wallets[session['user_id']] = wallet_address

            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid session'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_flask():
    """Run Flask app in background"""
    app.run(host='0.0.0.0', port=5000, debug=False)

# Start command with inline keyboard
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        keyboard = [
            [InlineKeyboardButton("📖 About BlockDAG", callback_data="about"),
             InlineKeyboardButton("💰 Current Price", callback_data="price")],
            [InlineKeyboardButton("🛒 Buy BDAG", callback_data="buy"),
             InlineKeyboardButton("⛏️ Mine BDAG", callback_data="mine")],
            [InlineKeyboardButton("🦊 Connect Wallet", callback_data="connect"),
             InlineKeyboardButton("💎 Check Balance", callback_data="balance")],
            [InlineKeyboardButton("📜 Transaction History", callback_data="history"),
             InlineKeyboardButton("📄 Whitepaper", callback_data="whitepaper")],
            [InlineKeyboardButton("🔄 Refresh Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 *Welcome to BlockDAG Bot!* 🚀\n\n"
            "🌟 Your gateway to the BlockDAG ecosystem\n"
            "💎 Buy, mine, and manage your BDAG tokens\n"
            "🦊 Connect your MetaMask wallet securely\n\n"
            "Choose an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# All functionality is now handled through inline keyboards

# Handle button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.callback_query.data or not update.callback_query.message:
        return

    query = update.callback_query
    await query.answer()

    # Main menu options
    if query.data == "start":
        await start_inline(update, context)
    elif query.data == "about":
        await about_inline(update, context)
    elif query.data == "price":
        await price_inline(update, context)
    elif query.data == "buy":
        await buy_bdag_inline(update, context)
    elif query.data == "mine":
        await mine_bdag_inline(update, context)
    elif query.data == "whitepaper":
        await whitepaper_inline(update, context)
    elif query.data == "connect":
        await connect_wallet_inline(update, context)
    elif query.data == "balance":
        await check_balance_inline(update, context)
    elif query.data == "history":
        await transaction_history_inline(update, context)

    # Handle buy buttons
    elif query.data.startswith("buy_"):
        amount_usd = query.data.split("_")[1]
        tokens = int(float(amount_usd) / BDAG_PRESALE_PRICE)

        back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(back_keyboard)

        await query.message.edit_text(
            f"✅ *Purchase Selected*\n\n"
            f"💰 Amount: ${amount_usd}\n"
            f"🪙 Tokens: {tokens:,} BDAG\n"
            f"💳 Price: ${BDAG_PRESALE_PRICE} per token\n\n"
            f"🌐 Complete your purchase at:\n"
            f"https://purchase3.blockdag.network/\n\n"
            f"⚠️ *Steps:*\n"
            f"1. Visit the official portal\n"
            f"2. Select payment method (BTC/ETH/BNB/USDT)\n"
            f"3. Get unique payment address (20min validity)\n"
            f"4. Send exact amount to address\n"
            f"5. Tokens delivered after mainnet launch",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # Handle wallet connection buttons
    elif query.data == "connect_new":
        await connect_wallet_inline(update, context)

    elif query.data == "disconnect_wallet":
        if update.effective_user and update.effective_user.id in user_wallets:
            del user_wallets[update.effective_user.id]

            back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
            reply_markup = InlineKeyboardMarkup(back_keyboard)

            await query.message.edit_text(
                "🔓 *Wallet Disconnected*\n\n"
                "Your MetaMask wallet has been disconnected successfully!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    elif query.data.startswith("check_status_"):
        session_id = query.data.replace("check_status_", "")
        if session_id in wallet_sessions:
            session = wallet_sessions[session_id]
            if session['status'] == 'connected':
                back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
                reply_markup = InlineKeyboardMarkup(back_keyboard)

                await query.message.edit_text(
                    f"✅ *Wallet Connected Successfully!*\n\n"
                    f"📱 Address: `{session['wallet_address']}`\n"
                    f"🔗 Your MetaMask wallet is now linked to your Telegram account!",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                # Clean up session
                del wallet_sessions[session_id]
            else:
                await query.answer("⏳ Connection still pending... Please complete in browser first.")
        else:
            await query.answer("❌ Session expired. Please try connecting again.")

# Inline versions of all functions
async def start_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📖 About BlockDAG", callback_data="about"),
         InlineKeyboardButton("💰 Current Price", callback_data="price")],
        [InlineKeyboardButton("🛒 Buy BDAG", callback_data="buy"),
         InlineKeyboardButton("⛏️ Mine BDAG", callback_data="mine")],
        [InlineKeyboardButton("🦊 Connect Wallet", callback_data="connect"),
         InlineKeyboardButton("💎 Check Balance", callback_data="balance")],
        [InlineKeyboardButton("📜 Transaction History", callback_data="history"),
         InlineKeyboardButton("📄 Whitepaper", callback_data="whitepaper")],
        [InlineKeyboardButton("🔄 Refresh Menu", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text(
        "👋 *Welcome to BlockDAG Bot!* 🚀\n\n"
        "🌟 Your gateway to the BlockDAG ecosystem\n"
        "💎 Buy, mine, and manage your BDAG tokens\n"
        "🦊 Connect your MetaMask wallet securely\n\n"
        "Choose an option below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def about_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(back_keyboard)

    await update.callback_query.message.edit_text(
        "📖 *About BlockDAG*\n\n"
        "BlockDAG is a hybrid Layer 1 blockchain that combines Bitcoin's security with Directed Acyclic Graph (DAG) technology. "
        "It offers enhanced scalability, faster transactions, and reduced fees.\n\n"
        "🏗️ Currently in presale phase\n"
        "⛏️ Proof-of-Work consensus\n"
        "🚀 Multiple transactions processed simultaneously\n"
        "💰 $380M+ raised in presale",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def price_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(back_keyboard)

    await update.callback_query.message.edit_text(
        f"💰 *Current BlockDAG Price*\n\n"
        f"🪙 Presale Price: ${BDAG_PRESALE_PRICE} per BDAG\n"
        f"📈 Total Raised: $380+ Million\n"
        f"💵 Minimum Purchase: ${MIN_PURCHASE_USD}\n"
        f"🎯 Launch Target: $0.05 (3,033% potential gain)\n\n"
        f"💳 Accepted: BTC, ETH, BNB, USDT, KAS, DOGE\n"
        f"📊 Token Holders: 200,000+",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def buy_bdag_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tokens_15 = int(15 / BDAG_PRESALE_PRICE)
    tokens_50 = int(50 / BDAG_PRESALE_PRICE)
    tokens_100 = int(100 / BDAG_PRESALE_PRICE)
    tokens_500 = int(500 / BDAG_PRESALE_PRICE)

    keyboard = [
        [InlineKeyboardButton(f"${15} = {tokens_15:,} BDAG", callback_data="buy_15")],
        [InlineKeyboardButton(f"${50} = {tokens_50:,} BDAG", callback_data="buy_50")],
        [InlineKeyboardButton(f"${100} = {tokens_100:,} BDAG", callback_data="buy_100")],
        [InlineKeyboardButton(f"${500} = {tokens_500:,} BDAG", callback_data="buy_500")],
        [InlineKeyboardButton("🌐 Official Purchase Portal", url="https://purchase3.blockdag.network/")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text(
        f"🛒 *Buy BlockDAG Tokens*\n\n"
        f"💰 Current Price: ${BDAG_PRESALE_PRICE} per BDAG\n"
        f"💵 Minimum: ${MIN_PURCHASE_USD}\n\n"
        f"💳 Payment Methods:\n"
        f"• Bitcoin (BTC)\n"
        f"• Ethereum (ETH)\n"
        f"• Binance Coin (BNB)\n"
        f"• Tether (USDT)\n"
        f"• Kaspa (KAS)\n"
        f"• Dogecoin (DOGE)\n\n"
        f"Choose amount or visit official portal:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def mine_bdag_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📱 Download X1 Mobile Miner", url="https://blockdag.network/product/blockdagx1")],
        [InlineKeyboardButton("⚡ X10 Hardware Miner", url="https://blockdag.network/product/blockdagx10")],
        [InlineKeyboardButton("🏭 View All Miners", url="https://blockdag.network")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text(
        "⛏️ *Mine BlockDAG*\n\n"
        "*Mobile Mining (FREE):*\n"
        "📱 X1 App - Up to 20 BDAG/day\n"
        "📲 iOS & Android available\n"
        "👥 3+ million users mining\n"
        "💡 Just tap daily lightning button\n\n"
        "*Hardware Mining:*\n"
        "⚡ X10 Miner - 200 BDAG/day (~$400)\n"
        "🔥 X30 Miner - 600 BDAG/day (~$1,800)\n"
        "🏭 X100 Miner - 2,000 BDAG/day (~$15,000)\n\n"
        "📦 19,400+ miners already shipped!\n"
        "🌍 Available in 130+ countries",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def whitepaper_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(back_keyboard)

    await update.callback_query.message.edit_text(
        "📄 *BlockDAG Resources*\n\n"
        "📖 Whitepaper: https://blockdag.network/blockdag-litepaper-r1.pdf"
        "🌐 Official Website: https://blockdag.network\n"
        "📊 Purchase Portal: https://purchase3.blockdag.network\n"
        "📱 Mining App: Search 'BlockDAG X1' in app stores\n"
        "📚 Wiki: https://wiki.blockdag.network",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def connect_wallet_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    user_id = update.effective_user.id

    # Check if user already has a connected wallet
    if user_id in user_wallets:
        keyboard = [
            [InlineKeyboardButton("🔄 Connect New Wallet", callback_data="connect_new")],
            [InlineKeyboardButton("❌ Disconnect Current", callback_data="disconnect_wallet")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            f"🔗 *Wallet Already Connected*\n\n"
            f"📱 Address: `{user_wallets[user_id]}`\n\n"
            f"Choose an option:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Generate unique session ID
    session_id = str(uuid.uuid4())
    wallet_sessions[session_id] = {
        'user_id': user_id,
        'status': 'pending',
        'wallet_address': None
    }

    # Create connection URL
    domain = get_domain()
    connect_url = f"{domain}/connect-wallet/{session_id}"

    # Generate QR code
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(connect_url)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        keyboard = [
            [InlineKeyboardButton("🦊 Open MetaMask Connection", url=connect_url)],
            [InlineKeyboardButton("✅ Check Connection Status", callback_data=f"check_status_{session_id}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Delete the previous message and send new photo with QR code
        await update.callback_query.message.delete()

        # Send QR code image
        if update.callback_query.message.chat:
            await context.bot.send_photo(
                chat_id=update.callback_query.message.chat.id,
                photo=img_buffer,
                caption="🦊 *Connect Your MetaMask Wallet*\n\n"
                        "**Method 1:** 📱 Scan this QR code with your phone\n"
                        "**Method 2:** 🖱️ Click the button below\n\n"
                        "🔒 Your wallet will be securely linked to your Telegram account\n"
                        "⏰ This connection link expires in 10 minutes\n\n"
                        "After connecting, click 'Check Connection Status'",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        # Fallback to text message if QR code generation fails
        keyboard = [
            [InlineKeyboardButton("🦊 Open MetaMask Connection", url=connect_url)],
            [InlineKeyboardButton("✅ Check Connection Status", callback_data=f"check_status_{session_id}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.message.edit_text(
            "🦊 *Connect Your MetaMask Wallet*\n\n"
            "📱 Click the button below to connect\n"
            "🔒 Your wallet will be securely linked\n"
            "⏰ Connection link expires in 10 minutes\n\n"
            "After connecting, click 'Check Connection Status'",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def check_balance_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(back_keyboard)

    if user_id not in user_wallets:
        await update.callback_query.message.edit_text(
            "⚠️ *No Wallet Connected*\n\n"
            "Please connect your MetaMask wallet first to check balance.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    wallet_address = user_wallets[user_id]
    try:
        balance_wei = w3.eth.get_balance(wallet_address)
        balance_bdag = w3.from_wei(balance_wei, 'ether')
        await update.callback_query.message.edit_text(
            f"💰 *Wallet Balance*\n\n"
            f"📱 Address: `{wallet_address}`\n"
            f"💎 Balance: {balance_bdag} BDAG",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.callback_query.message.edit_text(
            f"⚠️ *Error Fetching Balance*\n\n"
            f"Could not retrieve balance: {str(e)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def transaction_history_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(back_keyboard)

    if user_id not in user_wallets:
        await update.callback_query.message.edit_text(
            "⚠️ *No Wallet Connected*\n\n"
            "Please connect your MetaMask wallet first to view transaction history.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    wallet_address = user_wallets[user_id]
    try:
        url = EXPLORER_API.format(wallet_address)
        response = requests.get(url).json()

        if "result" not in response or len(response["result"]) == 0:
            await update.callback_query.message.edit_text(
                "📭 *No Transactions Found*\n\n"
                "Your wallet has no transaction history yet.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        txs = response["result"][:5]  # Show last 5
        message = f"📜 *Last 5 Transactions*\n\n"
        for tx in txs:
            tx_hash = tx["hash"]
            value = w3.from_wei(int(tx["value"]), "ether")
            message += f"🔹 Hash: `{tx_hash[:10]}...`\n   Amount: {value} BDAG\n\n"

        await update.callback_query.message.edit_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.callback_query.message.edit_text(
            f"⚠️ *Error Fetching History*\n\n"
            f"Could not retrieve transactions: {str(e)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# Main
def main():
    # Start Flask app in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    app_telegram = Application.builder().token(BOT_TOKEN).build()

    # Add only the start command handler - everything else is inline keyboard
    app_telegram.add_handler(CommandHandler("start", start))

    # Add callback query handler for buttons
    app_telegram.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot is running...")
    print("🌐 Web interface available for MetaMask connections")
    app_telegram.run_polling()

if __name__ == "__main__":
    main()
