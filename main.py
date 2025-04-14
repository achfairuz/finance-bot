import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,  ConversationHandler, MessageHandler, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import matplotlib.pyplot as plt
from io import BytesIO
import os


# Setup Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("financeBot").sheet1  # sesuaikan nama spreadsheet

# URL form submit (perhatikan: bukan "viewform", tapi "formResponse")
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfRJmrFp5gbzE8AydN8gzWfPzlThTzmQlwKBoRXPUeMELSQ7A/formResponse"

# Entry ID tiap field
ENTRY_TANGGAL     = "entry.1485889607"
ENTRY_JENIS       = "entry.109564056"
ENTRY_JUMLAH      = "entry.1384677978"
ENTRY_KETERANGAN  = "entry.1280307829"

TANGGAL, JENIS, JUMLAH, KETERANGAN = range(4)



# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 Tambah Data", callback_data='form')],
        [InlineKeyboardButton("📊 Lihat Rekap", callback_data='rekap')],
        [InlineKeyboardButton("ℹ️ Bantuan", callback_data='bantuan')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Hai! Silakan pilih menu:", reply_markup=reply_markup)
    
def buat_grafik_keuangan(records):
    import matplotlib.pyplot as plt
    from io import BytesIO

    if not records:
        return None

    # Hitung total masuk dan keluar per tanggal
    data = {}
    for r in records:
        tanggal = r["tanggal"]
        jumlah = int(r["jumlah"])
        jenis = r["jenis"].lower()

        if tanggal not in data:
            data[tanggal] = {"masuk": 0, "keluar": 0}

        data[tanggal][jenis] += jumlah

    # Siapkan data untuk grafik
    tanggal_list = sorted(data.keys())
    masuk_list = [data[t]["masuk"] for t in tanggal_list]
    keluar_list = [data[t]["keluar"] for t in tanggal_list]

    # Buat grafik
    plt.figure(figsize=(10, 6))
    plt.plot(tanggal_list, masuk_list, label="Masuk", marker='o', color='green')
    plt.plot(tanggal_list, keluar_list, label="Keluar", marker='o', color='red')
    plt.xlabel("Tanggal")
    plt.ylabel("Jumlah (Rp)")
    plt.title("📊 Grafik Keuangan")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Simpan grafik ke memory
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    return buf

def hitung_rekap(records):
    total_masuk = sum(int(r["jumlah"]) for r in records if r["jenis"].lower() == "masuk")
    total_keluar = sum(int(r["jumlah"]) for r in records if r["jenis"].lower() == "keluar")
    saldo = total_masuk - total_keluar

    teks = (
        f"💰 Rekap Keuangan:\n"
        f"Total Masuk: Rp {total_masuk:,}\n"
        f"Total Keluar: Rp {total_keluar:,}\n"
        f"Saldo Sekarang: Rp {saldo:,}"
    )
    return teks



# Command /rekap - total pengeluaran & pemasukan
async def rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()
    teks_rekap = hitung_rekap(records)
    grafik_buf = buat_grafik_keuangan(records)

    if grafik_buf:
        await update.message.reply_photo(photo=grafik_buf, caption=teks_rekap)
    else:
        await update.message.reply_text(teks_rekap)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "form":
        # trigger conversation form dari button
        await query.message.reply_text("📋 Oke, mari kita isi form...\nKetik tanggal (YYYY-MM-DD):")
        context.user_data["form_state"] = TANGGAL
        return TANGGAL

    elif query.data == "rekap":
        records = sheet.get_all_records()
        total_masuk = sum([r["jumlah"] for r in records if r["jenis"].lower() == "masuk"])
        total_keluar = sum([r["jumlah"] for r in records if r["jenis"].lower() == "keluar"])
        saldo = total_masuk - total_keluar

        await query.edit_message_text(
            f"💰 Rekap Keuangan:\n"
            f"Total Masuk: Rp {total_masuk:,}\n"
            f"Total Keluar: Rp {total_keluar:,}\n"
            f"Saldo Sekarang: Rp {saldo:,}"
        )

    elif query.data == "bantuan":
        await query.edit_message_text(
            "📌 Kamu bisa tambah data keuangan dengan cara:\n"
            "- Tekan 'Tambah Data' di menu\n"
            "- Atau ketik perintah manual:\n"
            "`/submit 2025-04-15 keluar 10000 beli kopi`\n\n"
            "Untuk melihat rekap, tekan 'Lihat Rekap'."
        )

        
async def form_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Masukkan tanggal (YYYY-MM-DD):")
    return TANGGAL

async def input_tanggal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tanggal"] = update.message.text
    await update.message.reply_text("💸 Jenis transaksi? (masuk/keluar):")
    return JENIS

async def input_jenis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jenis = update.message.text.lower()
    if jenis not in ["masuk", "keluar"]:
        await update.message.reply_text("❗ Hanya 'masuk' atau 'keluar'. Coba lagi:")
        return JENIS
    context.user_data["jenis"] = jenis
    await update.message.reply_text("💰 Masukkan jumlah:")
    return JUMLAH

async def input_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["jumlah"] = update.message.text
    await update.message.reply_text("📝 Masukkan keterangan:")
    return KETERANGAN

async def input_keterangan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["keterangan"] = update.message.text

    payload = {
        ENTRY_TANGGAL: context.user_data["tanggal"],
        ENTRY_JENIS: context.user_data["jenis"],
        ENTRY_JUMLAH: context.user_data["jumlah"],
        ENTRY_KETERANGAN: context.user_data["keterangan"]
    }

    response = requests.post(FORM_URL, data=payload)

    if response.status_code == 200:
        await update.message.reply_text("✅ Data berhasil dikirim ke Google Form!")
    else:
        await update.message.reply_text("❌ Gagal kirim data. Cek koneksi.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Pengisian dibatalkan.")
    return ConversationHandler.END


# Setup Bot
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("rekap", rekap))
app.add_handler(CallbackQueryHandler(button_handler))
form_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("form", form_start),
        CallbackQueryHandler(button_handler, pattern="^form$")
    ],
    states={
        TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_tanggal)],
        JENIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_jenis)],
        JUMLAH: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_jumlah)],
        KETERANGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_keterangan)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)


app.add_handler(form_conv_handler)


print("Bot keuangan via Google Form berjalan...")
app.run_polling()

