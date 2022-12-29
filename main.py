import aiohttp
import asyncio
import json
import time
import os
import filecmp
import zipfile
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

url = "https://eu.wotblitz.com/en/api/events/items/auction/?page_size=50&type[]=vehicle&saleable=true"
#url = "https://tanksblitz.ru/ru/api/events/items/auction/?page_size=50&type[]=vehicle&saleable=true" # For TanksBlitz
webhookURL = "Your Webhook URL"
messageID = None

# Make request on the url
async def fetch(session, url):
    async with session.get(url) as response:
        data = await response.text()
        return data

# Parse the response
async def parse(response):
    data = response
    return data

async def getNumberofTanks():
    async with aiohttp.ClientSession() as session:
        response = await fetch(session, url)
        await parse(response)

        iList = [] # reset list

        urldata = (await parse(response))
        json_object = json.loads(urldata)

        for i in range(0, json_object['count']):
            if 'current_count' in json_object['results'][i]:
                if json_object['results'][i]['current_count'] > 0 and json_object['results'][i]['available'] != False:
                    iList.append(i)
        #print("Successfully got list of tanks: " + str(len(iList)))

        with open('data.json', 'w') as outfile:
            json.dump(json_object, outfile)
        outfile.close()

        if not os.path.exists('./log/'):
            os.makedirs('./log/')

        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d-%H-%M-%S")
        with open('./log/'+ dt_string + '.json', 'w') as outfile:
            json.dump(json_object, outfile)
        outfile.close()

        if not os.path.exists('./log/log.zip'):
            with zipfile.ZipFile('./log/log.zip', 'w') as myzip:
                myzip.write('./log/' + dt_string + '.json')
        else:
            with zipfile.ZipFile('./log/log.zip', 'a') as myzip:
                myzip.write('./log/' + dt_string + '.json')
        os.remove('./log/' + dt_string + '.json')
        return iList, json_object

async def getTankInfo(i, json_object):
    if 'results' not in json_object:
        return None, None, None, None, 0, None, None
    tankname = json_object['results'][i]['entity']['user_string']
    tankprice = json_object['results'][i]['price']['value']
    next_price = "n/a"
    if 'next_price' in json_object['results'][i]:
        if json_object['results'][i]['next_price'] is not None:
            next_price = json_object['results'][i]['next_price']['value']
    roman_level = json_object['results'][i]['entity']['roman_level']
    current_count = json_object['results'][i]['current_count']
    initial_count = json_object['results'][i]['initial_count']
    available_before = json_object['results'][i]['available_before']
    available_before = datetime.strptime(available_before, '%Y-%m-%dT%H:%M:%S')
    #print("Got tank ID " + str(i) + ", name: " + tankname)

    return tankname, tankprice, next_price, roman_level, current_count, initial_count, available_before

async def compareForChanges():
    changed = False
    old = "./data_old.json"
    new = "./data.json"

    if not os.path.exists(old):
        f = open(old, "w")
        f.write("{}")
        f.close()

    changed = filecmp.cmp(old, new, shallow=False)
    changed = not changed

    return changed
async def renameOld():
    old = "./data_old.json"
    new = "./data.json"
    if os.path.exists(old):
        os.remove(old)
    os.rename(new, old)

async def getDataOld():
    with open('data_old.json') as json_file:
        data = json.load(json_file)
    return data

async def send_webhook_embed(iList, json_object):
    webhook = DiscordWebhook(url=webhookURL, content='')
    embed = DiscordEmbed(title='WoTB Auction', description='https://eu.wotblitz.com/en/auction/#/\nhttps://na.wotblitz.com/en/auction/#/\nhttps://asia.wotblitz.com/en/auction/#/', color='03b2f8')
    embed.set_timestamp()
    ping = False
    global messageID
    changed = await compareForChanges()
    

    for i in range(0, len(iList)):
        tankInfo = await getTankInfo(iList[i], json_object)
        if tankInfo[4] < 100:
            ping = True
        #tankname, tankprice, next_price, roman_level, current_count, initial_count
        embed.add_embed_field(name='__{0} ({1})__'.format(tankInfo[0], tankInfo[3]), value= "**Current price:** {0} golds\n**Upcoming price:** {1} golds\n**Vehicles left:** {2}/{3}\n **In auction till** {4}".format(tankInfo[1], tankInfo[2], tankInfo[4], tankInfo[5], tankInfo[6]))

    if ping != False:
        webhook = DiscordWebhook(url=webhookURL, content='**Attention! Some tanks already have less than 100 pieces**') # Role ping if needed '\n<@&1057672078448402473>')
    else:
        webhook = DiscordWebhook(url=webhookURL)
    webhook.add_embed(embed)
    
    if changed != False:
        dataOld = await getDataOld()
        
        embed2 = DiscordEmbed(title='Changes in auction!', color='ff0000')
        embed2.set_timestamp()
        embed2.set_footer(text='Created by GonnaHetzMe#1440', icon_url='https://cdn.discordapp.com/avatars/297059785155543041/e09a6d2fa0fd915b1d019d265b322e06.gif')
        for i in range(0, len(iList)):
            tankInfo = await getTankInfo(iList[i], json_object)
            oldTankInfo = await getTankInfo(iList[i], dataOld)
            diffence = oldTankInfo[4] - tankInfo[4]
            if diffence > 0:
                amount = ['piece', 'pieces']
                be = ['was', 'were']
                if diffence == 1:
                    amount = amount[0]
                    be = be[0]
                else:
                    amount = amount[1]
                    be = be[1]
                embed2.add_embed_field(name='__{0} ({1})__'.format(tankInfo[0], tankInfo[3]), value= "{0} {1} {2} sold".format(diffence, amount, be))

        webhook.add_embed(embed2)
    if changed != False:
        if messageID != None:
            webhook.id = messageID
            webhook.delete()
        response = webhook.execute()
        messageID = webhook.id
        print("Successfully sent webhook", response)
    else:
        print("No changes, not sending webhook")
    await renameOld()

async def main():
    numOfTanks = await getNumberofTanks()
    await send_webhook_embed(numOfTanks[0], numOfTanks[1])

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    #Pterodactyl starting message
    print("Script successfully loaded")
    while True:
        loop.run_until_complete(main())
        time.sleep(60)