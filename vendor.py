from deepdiff import DeepDiff
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup, Tag
from discord_webhook import DiscordWebhook, DiscordEmbed

import re
import os
import sys
import csv
import json
import time

import smtplib
from email.mime.text import MIMEText

"""
TODO
    * Better error handling
    * Reduce file i/o (rushed thru this)
    * Make more reusable logic
    * Logging
    * Find a way to filter old tracked items
"""

PORT = 587
SERVER = "smtp.gmail.com"
SENDER = "my.personal.weather.man.bot@gmail.com"
PASSWORD = os.environ.get("DISCORD_BOT_GMAIL_PWD")
SUBJECT = "Subject"
FROM = "From"
TO = "To"


VENDOR_URL = "vendor_url"
TRACKING_HEADERS = ["User", "Item Name", "Timestamp"]

def read_config():
    config = None
    with open("config.json", "r") as f:
        config = json.load(f)
        config["webhook_url"] = os.environ.get("DISCORD_BOT_WEBHOOK_URL")
    return config

def format_gear_embed(item):
    embed = DiscordEmbed(title=item['Name'], color=0x00ff00)
    embed.set_description("Item Available ✅")
    embed.add_embed_field(name='Location', value=item['Location'], inline=False)
    embed.add_embed_field(name='Gear Set', value=item['Gear Set'], inline=False)
    embed.add_embed_field(name='Slot', value=item['Slot'], inline=False)
    embed.add_embed_field(name='Slot Details', value=item['Slot Details'], inline=False)
    embed.add_embed_field(name='Talent', value=item['Talent'], inline=False)
    embed.add_embed_field(name='Attributes', value='\n'.join(item['Attributes']), inline=False)
    return embed

def format_weapon_embed(item):
    embed = DiscordEmbed(title=item['Name'], color=0x00ff00)
    embed.set_description("Item Available ✅")
    embed.add_embed_field(name='Location', value=item['Location'], inline=False)
    embed.add_embed_field(name='Talent', value=item['Talent'], inline=False)
    embed.add_embed_field(name='Damage', value=item['Damage'], inline=False)
    embed.add_embed_field(name='RPM', value=item['RPM'], inline=False)
    embed.add_embed_field(name='Mag Size', value=item['Mag Size'], inline=False)
    return embed

def format_mod_embed(item):
    embed = DiscordEmbed(title=item['Name'], color=0x00ff00)
    embed.set_description("Item Available ✅")
    embed.add_embed_field(name='Location', value=item['Location'], inline=False)
    embed.add_embed_field(name='Details', value=item['Details'], inline=False)
    return embed

def send_vendor_info(webhook_url, item_type, data):
    embeds = []
    if item_type == "gear":
        for item in data:
            embeds.append(format_gear_embed(item))
    elif item_type == "weapon":
        for item in data:
            embeds.append(format_weapon_embed(item))
    elif item_type == "mod":
        for item in data:
            embeds.append(format_mod_embed(item))
    
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i + 10]
        webhook = DiscordWebhook(url=webhook_url, embeds=batch)
        response = webhook.execute()
        print(response)

def get_vendor_reset_html(vendor_url):
    # Set up Chrome WebDriver
    service = Service(executable_path="/usr/bin/chromedriver")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Load the webpage
    driver.get(vendor_url)

    # Wait for dynamic content to load (you may need to adjust the waiting time as needed)
    driver.implicitly_wait(10)

    # Extract the HTML content after JavaScript execution
    html_content = driver.page_source

    # Quit the WebDriver
    driver.quit()

    with open("vendor_reset.html", "w", encoding="utf") as f:
        f.write(html_content)

    return html_content

def get_vendor_reset_info(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    gear_data = []
    weapon_data = []
    mod_data = []

    sections = soup.find_all(class_="section group")
    for section in sections:
        divs = section.find_all("div")
        for div in divs:
            tables = div.find_all("table")

            item_data = []
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    spans = row.find_all("span")
                    row_data = []
                    cells = []
                    if len(spans) >= 2:
                        td = row.find("td")
                        tags = td.contents
                        row_data = [tag.strip() for tag in tags if not isinstance(tag, Tag)]
                    else:
                        cells = row.find_all(["td", "th"])
                        row_data = [cell.get_text(strip=True) for cell in cells]
                    item_data.append(row_data)
            
            if section.get("id") == "division-gears":
                item_props = {
                    "Name": item_data[0][0],
                    "Gear Set": item_data[1][0],
                    "Location": item_data[2][0],
                    "Slot": item_data[3][1],
                    "Slot Details": item_data[4][0] + " " + item_data[4][1],
                    "Type": "gear"
                }
                attributes = []
                for p in item_data[5:-1]:
                    attributes += p
                item_props.update({"Attributes": attributes, "Talent": item_data[len(item_data)-1][0]})
                gear_data.append(item_props)
            elif section.get("id") == "division-weapons":
                item_props = {
                    "Name": item_data[0][0],
                    "Location": item_data[1][0],
                    "Talent": item_data[3][1],
                    "Damage": item_data[5][0],
                    "RPM": item_data[5][1],
                    "Mag Size": item_data[5][2],
                    "Type": "weapon"
                }
                attributes = []
                for p in item_data[6:]:
                    attributes += p
                item_props.update({"Attributes": attributes})
                weapon_data.append(item_props)
            elif section.get("id") == "division-mods":
                detail_str = item_data[2][0]
                match = re.search(r'\d', detail_str)
                if match:
                    index = match.start()
                    # Insert a space before the number
                    detail_str = detail_str[:index] + ' ' + detail_str[index:]
                item_props = {
                    "Name": item_data[0][0],
                    "Location": item_data[1][0],
                    "Details": detail_str.strip(),
                    "Type": "mod"
                }
                mod_data.append(item_props)

    return gear_data, weapon_data, mod_data


def check_if_reset(data):
    if not os.path.exists("vendor.json"):
        with open("vendor.json", "w") as vf:
            vf.write("{}")
    with open("vendor.json", "r") as f:
        existing = json.load(f)
    diff = DeepDiff(data, existing, ignore_order=True)
    is_reset = bool(diff)
    print(is_reset)
    return is_reset


# If item_name is provided, it will look for only a single item with that name
def find_tracked_items(data, rt_track_info=None):
    tracked = []
    if rt_track_info is None:
        with open("tracking.csv", "r") as f:
            reader = csv.DictReader(f)
            tracked = list(reader)
    else:
        tracked.append(rt_track_info)

    items = []
    vendor_data_dict = {}

    all_vendor_data = data.get("gear", []) + data.get("weapon", []) + data.get("mod", [])
    for item in all_vendor_data:
        vendor_data_dict.update({item.get("Name"): item})
    
    for track_info in tracked:
        track_info_name = track_info.get("Item Name")
        if track_info_name in vendor_data_dict:
            items.append({"track_info": track_info, "item": vendor_data_dict.get(track_info_name)})

    return items


def notify_channel_items_found(items_found, webhook_url):
    embeds = []
    for info in items_found:
        item = info.get("item")
        item_type = item.get("Type")

        if item_type == "gear":
            embeds.append(format_gear_embed(item))
        elif item_type == "weapon":
            embeds.append(format_weapon_embed(item))
        elif item_type == "mod":
            embeds.append(format_mod_embed(item))

    for i in range(0, len(embeds), 10):
        batch = embeds[i:i + 10]
        webhook = DiscordWebhook(url=webhook_url, embeds=batch)
        response = webhook.execute()
        print(response)
        time.sleep(5)


def notify_channel_vendor_reset(webhook_url):
    time.sleep(5)
    webhook = DiscordWebhook(url=webhook_url, content="ℹ️ ATTENTION - VENDORS HAVE RESET THEIR ITEMS! ℹ️")
    print(webhook.execute())


def update_tracking_info(items_found):
    with open("tracking.csv", "r") as rf:
        reader = csv.DictReader(rf)
        tracked = list(reader)
    track_info = [info.get("track_info") for info in items_found]
    name_set = set([item.get("Item Name") for item in track_info])
    filtered = list(filter(lambda x: x.get("Item Name") not in name_set, tracked))
    
    with open("tracking.csv", "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=TRACKING_HEADERS, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(filtered)


# Used by discord bot to track an item
def track_item(user, item_name):
    with open("tracking.csv", "r") as rf:
        reader = csv.DictReader(rf)
        tracked = list(reader)
    if len(tracked) >= 100:
        # TODO: Better way to handle this
        return "exceeded"

    rt_track_info = {"User": user, "Item Name": item_name, "Timestamp": round(time.time() * 1000)}

    with open("vendor.json") as f:
        existing = json.load(f)

    items_found = find_tracked_items(existing, rt_track_info)

    # If items found, then respond immediately and don't track item
    if len(items_found) > 0:
        try:
            config = read_config()
            webhook_url = config.get("webhook_url")
            notify_channel_items_found(items_found, webhook_url)
            return True
        except Exception:
            print("Failed to read config")
            return False
    else: # Otherwise, track the item
        with open("tracking.csv", "a", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
            writer.writerow([user, item_name, rt_track_info.get("Timestamp")])
        return False
    

def untrack_item(item_name):
    with open("tracking.csv", "r") as rf:
        reader = csv.DictReader(rf)
        tracked = list(reader)
    tracked = list(filter(lambda x: x.get("Item Name") != item_name, tracked))
    
    with open("tracking.csv", "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=TRACKING_HEADERS, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(tracked)


def get_tracking():
    with open("tracking.csv", "r") as rf:
        reader = csv.DictReader(rf)
        tracked = list(reader)
    display = "Items currently being tracked:\n\n"
    for item in tracked:
        display += "🟢 %s - (created by %s)\n\n" % (item.get("Item Name"), item.get("User"))
    return display


def send_email(subj, msg, receivers):
    email_msg = MIMEText(msg)
    email_msg[SUBJECT] = subj
    email_msg[FROM] = SENDER
    email_msg[TO] = ", ".join(receivers)

    server = smtplib.SMTP(host=SERVER, port=PORT)
    server.ehlo()
    server.starttls()
    server.login(SENDER, PASSWORD)
    server.sendmail(SENDER, receivers, email_msg.as_string())
    server.quit()


def main():
    config = read_config()
    if config is None:
        raise Exception("Failed to read config")
    
    if not os.path.exists("tracking.csv"):
        with open("tracking.csv", "w", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=TRACKING_HEADERS, quoting=csv.QUOTE_NONNUMERIC)
            writer.writeheader()

    read_from_file = len(sys.argv) == 2 and sys.argv[1] == "from_file"

    gear_data, weapon_data, mod_data = {}, {}, {}

    if read_from_file:
        with open("vendor.json") as f:
            existing = json.load(f)
            gear_data = existing.get("gear")
            weapon_data = existing.get("weapon")
            mod_data = existing.get("mod")
    else:
        vendor_url = config.get(VENDOR_URL)
        vendor_html = get_vendor_reset_html(vendor_url)
        gear_data, weapon_data, mod_data = get_vendor_reset_info(vendor_html)

    data = {
        "gear": gear_data,
        "weapon": weapon_data,
        "mod": mod_data
    }

    # TODO: Clean up this logic to avoid multiple reads to tracking.csv
    is_reset = check_if_reset(data)
    if is_reset:
        notify_channel_vendor_reset(config.get("webhook_url"))
    else:
        items_found = find_tracked_items(data)
        update_tracking_info(items_found)
        if len(items_found) > 0:
            notify_channel_items_found(items_found, config.get("webhook_url"))

    receivers = ["dominic.fernandez1023@gmail.com"]
    send_email("D2 Vendor CRON Job", "Vendor Reset: " + str(is_reset), receivers)

    with open("vendor.json", "w") as f:
        json.dump(data, f)


if __name__ == "__main__":
    main()
