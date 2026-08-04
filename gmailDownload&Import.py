import imaplib
import email
import time
import keys
from email import utils
import psycopg2
IMAP_SERVER = "imap.gmail.com"

# Petlja ponavljanja skripte
def fetch_csv():
        import os
        # Povezivanje
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(keys.EMAIL_ACCOUNT, keys.APP_PASSWORD)
        mail.select("inbox")

        # Pronalazak svake pošte preko ID
        status, messages = mail.search(None, "UNSEEN")
        mail_ids = messages[0].split()

        if not mail_ids:
            print("No emails found.")
            return

        # Spremanje najnovije pošte
        latest_email_id = mail_ids[-1]

        # Izdvajanje poveznica/dokumenta u pošti
        status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                # Provjera pošiljatelja
                sender_address = email.utils.parseaddr(msg.get('from'))[1]
                if sender_address != keys.allowed_sender:
                    print(f"{sender_address} is invalid!")
                    continue
                print("Subject:", msg.get("Subject"))

                # Prođi sve dijelove pošte
                from email.header import decode_header
                for part in msg.walk():
                    raw_filename = part.get_filename()
                    if raw_filename:
                        # Dekodiranje dokumenta (Neobavezno)
                        decoded_parts = decode_header(raw_filename)
                        filename = ""
                        for part_str, encoding in decoded_parts:
                            if isinstance(part_str, bytes):
                                filename += part_str.decode(encoding or "utf-8")
                            else:
                                filename += part_str
                        print("Decoded filename:", filename)

                        # AKO JE CSV SPREMANJE NA RAČUNALO
                        if filename.lower().endswith(".csv"):
                            filepath = os.path.join(keys.SAVE_PATH, filename)
                            with open(filepath, "wb") as csvfile:
                                csvfile.write(part.get_payload(decode=True))
                            print(f"Saved CSV: {filepath}")
        mail.logout()

        import os
        import glob
        import csv
        from datetime import datetime

        connect = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="1234",
            host="localhost",
            port="3307"
        )
        cursor = connect.cursor()

        files = glob.glob(os.path.join(keys.SAVE_PATH, "*.csv"))
        if not files:
            print("No CSV files found.")
            return

        newest_file = max(files, key=os.path.getctime)
        print("Using file:", newest_file)

        with open(newest_file, newline='', encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)
            for row in reader:
                if not row or len(row) < 5 or not row[0].strip():
                    continue
                try:
                    date_part = row[0].strip()
                    time_part = row[1].strip()
                    systolic = int(row[2])
                    diastolic = int(row[3])
                    pulse = int(row[4])
                    notes = row[5] if len(row) > 5 else None
                    dt = datetime.strptime(f"{date_part} {time_part}",
                                           "%b %d %Y %H:%M")
                    cursor.execute("""
                        INSERT INTO bp_gmail (time, systolic, diastolic, pulse, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (time) DO NOTHING
                    """, (dt, systolic, diastolic, pulse, notes))
                except Exception as e:
                    print("Skipping row:", row)
                    print("Error:", e)

        connect.commit()
        cursor.close()
        connect.close()
        print("Import complete.")
# PETLJA ZA POKRETANJE SVAKIH 10 SEKUNDI
while True:
    fetch_csv()
    print("Waiting 10 seconds...\n")
    time.sleep(10)