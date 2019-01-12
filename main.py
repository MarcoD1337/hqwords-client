import asyncio
import websockets
import json
import pyhq
import aioconsole
from os import system, name
from colorama import init, Fore, Style
from datetime import datetime
from random import choice, uniform

debug = True

init()

def outputMessage(msg):
    out = (f'{str(datetime.now()).split()[1][:8]} {msg}')
    print(out)
    if 'DEBUG' in msg:
        with open('game.log', 'a+') as f:
            f.write(f'{out}\n')

def loadJson(fn):
    try:
        with open(fn) as f:
            fr = json.load(f)
    except: fr = json.load("[]")
    return fr

def writeJson(fn, nd):
    try:
        with open(fn, 'w') as f:
            json.dump(nd, f, indent=2)
        return True
    except: return False

def clearOutput():
    system('cls' if name == 'nt' else 'clear')
    

def displayLogo():
    randomColors = [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.WHITE]
    color = choice(randomColors)
    with open('logo.txt', 'r') as f:
        print()
        for line in f:
            print (color + line, end='')
        print(Style.RESET_ALL + '\n')

def displayMainMenu():
    choice = None
    while True:
        clearOutput()
        displayLogo()
        print (f'{Fore.CYAN}[{Fore.WHITE}1{Fore.CYAN}] {Fore.WHITE}Play Game{Fore.CYAN}                [{Fore.WHITE}2{Fore.CYAN}] {Fore.WHITE}Account Setup{Fore.CYAN}               [{Fore.WHITE}3{Fore.CYAN}] {Fore.WHITE}Information')
        print(Style.RESET_ALL)
        choice = input("=> ")
        if not choice in ['1', '2', '3']:
            continue
        return choice

def menuSwitch():
    choice = int(displayMainMenu())
    if choice == 3:
        print ("\nCreated with love by SilliBird")
        print ("HQ Trivia is a registered trademark of Intermedia Labs.")
        input (f"\n{Fore.CYAN}Hit enter to continue. {Style.RESET_ALL}")
        menuSwitch()
    elif choice == 2:
        loginToken = input (f"\nNew login token to use: ")
        config = loadJson('config.json')
        config['login_token'] = loginToken
        writeJson('config.json', config)
        input (f"\n{Fore.CYAN}Hit enter to continue. {Style.RESET_ALL}")
        menuSwitch()
    elif choice == 1:
        config = loadJson('config.json')
        if not config['login_token']:
            print ("\nYou need to set a login token in the Account Setup")
            input (f"\n{Fore.CYAN}Hit enter to continue. {Style.RESET_ALL}")
            menuSwitch()
        asyncio.get_event_loop().run_until_complete(playGame())

async def cooldown():
	await asyncio.sleep(round(uniform(7.5, 8.5), 2))
	outputMessage(f"[HQ Words] {Fore.GREEN}It's safe to answer!{Style.RESET_ALL}")

async def playGame():
    loginToken = loadJson('config.json')['login_token']
    client = pyhq.HQClient(loginToken)
    outputMessage(f"[HQ Words] Connected as {Fore.YELLOW}{client.me().username}{Style.RESET_ALL} with a unclaimed balance of {Fore.YELLOW}{client.me().leaderboard.unclaimed}{Style.RESET_ALL}")
    schedule = client.schedule()
    if debug: outputMessage(f"[DEBUG] {schedule}")
    if not schedule['active'] == True or not schedule['showType'] == 'hq-words':
        outputMessage(f"[HQ Words] {Fore.YELLOW}Words isn't live.{Style.RESET_ALL}")
        input (f"\n{Fore.CYAN}Hit enter to continue. {Style.RESET_ALL}")
        menuSwitch()
    else:
        outputMessage(f"[HQ Words] {Fore.YELLOW}It's go time.{Style.RESET_ALL}")
    broadcastId = schedule['broadcast']['broadcastId']
    websocketURL = client.socket_url()
    subscribed = False
    puzzleState = ''
    async with websockets.connect(websocketURL, extra_headers={'Authorization': 'Bearer ' + client.auth_token}) as websocket:
        async for msg in websocket:
            try:
                obj = json.loads(msg.encode("utf-8"))
            except: pass
            if obj.get('itemId') == 'chat':
                if debug:
                    outputMessage(f'[DEBUG] Disabling chat.')
                await websocket.send(json.dumps({'type': 'chatVisibilityToggled', 'chatVisible': False}))
            elif debug and not obj.get('type') == 'broadcastStats' and not obj.get('type') == 'gameStatus':
                outputMessage(f'[DEBUG] {obj}')

            if not subscribed:
                subscribed = True
                await websocket.send(json.dumps({'type': 'subscribe', 'broadcastId': int(broadcastId), 'gameType': 'words'}))

            if obj.get('type') == 'showWheel':
                letter = obj.get('letters')[0]
                await asyncio.sleep(0.5)
                await websocket.send(json.dumps({'showId': int(obj.get('showId')), 'type': 'spin', 'nearbyIds': [], 'letter': letter}))
                outputMessage(f"[HQ Words] {Fore.YELLOW}Sent spun letter {letter}{Style.RESET_ALL}")

            if obj.get('type') == 'startRound':
                puzzleState = obj.get('puzzleState')
                outputMessage(f"[HQ Words] {Fore.YELLOW}{puzzleState}{Style.RESET_ALL}")
                asyncio.get_event_loop().create_task(cooldown())
                solution = await aioconsole.ainput("=> ")
                for char in set(list(solution.upper().replace(' ',''))):
                    for state in puzzleState:
                        if char in state:
                            continue
                    await websocket.send(json.dumps({'roundId': int(obj.get('roundId')), 'type': 'guess', 'showId': int(obj.get('showId')), 'letter': char}))
                    outputMessage(f"[HQ Words] {Fore.YELLOW}Guessed character {char}{Style.RESET_ALL}")
                outputMessage(f"[HQ Words] {Fore.YELLOW}Done solving!{Style.RESET_ALL}")

            if obj.get('type') == 'endRound':
                if obj.get('solved') == True:
                    outputMessage(f"[HQ Words] {Fore.YELLOW}Solved in {round(int(obj.get('completionTime')) * .001, 3)} seconds!{Style.RESET_ALL}")
                else:
                    outputMessage(f"[HQ Words] {Fore.YELLOW}Failed to solve :({Style.RESET_ALL}")


            if obj.get('type') == 'letterReveal':
                puzzleState = obj.get('puzzleState')
                outputMessage(f"[HQ Words] {Fore.YELLOW}{puzzleState}{Style.RESET_ALL}")

            await websocket.ping()

menuSwitch()