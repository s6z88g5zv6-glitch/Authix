import httpx
import requests
import time
import json
import colorama
from colorama import Fore, Style
import threading
import random
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import urllib3
import urllib.parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.system("title Discord Selfbot by drage_gg")
os.system("start https://discord.gg/jUfY2zNdkF")
colorama.init(autoreset=True)

# Proxy support
proxies = []
try:
    with open('proxies.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                proxies.append(line)
except FileNotFoundError:
    pass

def get_proxy():
    if not proxies:
        return None
    proxy = random.choice(proxies)
    return {'http': 'http://' + proxy, 'https': 'https://' + proxy}


try:
    with open('token.txt', 'r') as f:
        tokens = [line.strip() for line in f if line.strip()]
        if not tokens:
            print("token.txt is empty. Please add valid Discord tokens.")
            exit()
except FileNotFoundError:
    print("token.txt not found. Please create token.txt with your Discord tokens.")
    exit()

valid_tokens = tokens

TOKEN = valid_tokens[0]

# Get user IDs for each valid token
user_ids = []
for token in valid_tokens:
    try:
        headers_temp = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = httpx.get('https://discord.com/api/v9/users/@me', headers=headers_temp, verify=False)
        if response.status_code == 200:
            user_ids.append(response.json()['id'])
        else:
            print(Fore.YELLOW + f"Warning: Could not get user ID for token {token[:10]}... (status {response.status_code})")
    except Exception as e:
        print(Fore.YELLOW + f"Warning: Error getting user ID for token {token[:10]}...: {e}")

# Read owner IDs from owner.txt
try:
    with open('owner.txt', 'r') as f:
        owners = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print("owner.txt not found. Please create owner.txt with owner IDs.")
    exit()



# Headers for requests
headers = {
    'Authorization': TOKEN,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Global variables
autoping_active = False
autoping_thread = None
autoping_channel = None
chatpack_active = False
chatpack_thread = None
chatpack_channel = None
running = True
console_thread = None
current_voice_guild = None
last_message_ids = {}
processed_messages = set()
active_channels = set()
command_processed = False
last_refresh = 0

def get_all_channels():
    channels = []
    # Get all guilds the user is in
    url = 'https://discord.com/api/v9/users/@me/guilds'
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        guilds = response.json()
        for guild in guilds:
            guild_id = guild['id']
            # Get channels in the guild
            url_channels = f'https://discord.com/api/v9/guilds/{guild_id}/channels'
            response_channels = requests.get(url_channels, headers=headers, verify=False)
            if response_channels.status_code == 200:
                guild_channels = response_channels.json()
                for ch in guild_channels:
                    if ch['type'] == 0:  # text channel
                        channels.append(ch['id'])
    # Get DM channels
    url = 'https://discord.com/api/v9/users/@me/channels'
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        dms = response.json()
        for dm in dms:
            if dm['type'] == 1:  # DM
                channels.append(dm['id'])
    return channels

def send_message(channel_id, message):
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages'
    data = {'content': message}
    # Use all valid tokens concurrently for sending with proxy rotation to bypass rate limits
    results = []
    def send_with_token(token):
        headers_send = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ])
        }
        # Random headers to bypass detection
        headers_send['X-Super-Properties'] = 'eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJyZWxlYXNlX2NoYW5uZWwiOiJzdGFibGUiLCJjbGllbnRfdmVyc2lvbiI6IjEuMC45MDAxIiwib3NfdmVyc2lvbiI6IjEwLjAuMTkwNDIiLCJvc192ZXJzIjoiV2luZG93cyAxMCBEdWJpb24ifQ=='
        headers_send['X-Fingerprint'] = ''.join(random.choices('0123456789abcdef', k=32))
        headers_send['X-Context-Properties'] = ''.join(random.choices('0123456789abcdef', k=64))
        headers_send['X-Discord-Locale'] = random.choice(['en-US', 'en-GB', 'tr'])
        headers_send['X-Discord-Timezone'] = random.choice(['America/New_York', 'Europe/London', 'Europe/Istanbul'])
        headers_send['X-Requested-With'] = 'XMLHttpRequest'
        headers_send['Referer'] = 'https://discord.com/channels/@me'
        headers_send['Origin'] = 'https://discord.com'
        proxy = get_proxy()  # Use proxy to bypass rate limits
        max_retries = 10  # Reduced retries since proxies help
        backoff = 0.1
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers_send, data=json.dumps(data), timeout=10, proxies=proxy)
                if response.status_code == 200:
                    results.append(response.json())
                    break
                elif response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', str(backoff))
                    sleep_time = float(retry_after) if retry_after else backoff
                    sleep_time *= (1 + random.uniform(-0.1, 0.1))  # Jitter
                    time.sleep(max(sleep_time, 0.05))
                    backoff = min(backoff * 1.5, 5)  # Increase backoff
                    proxy = get_proxy()  # Rotate proxy on 429
                else:
                    proxy = get_proxy()  # Rotate proxy on other errors
                    time.sleep(backoff)
                    backoff = min(backoff * 1.2, 3)
            except requests.exceptions.RequestException as e:
                proxy = get_proxy()  # Rotate proxy on exception
                time.sleep(backoff)
                backoff = min(backoff * 1.2, 3)
    threads = []
    for token in valid_tokens:
        t = threading.Thread(target=send_with_token, args=(token,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return results if results else None

def send_embed(channel_id, title, description, color=0x00ff00):
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages'
    data = {
        'embeds': [{
            'title': title,
            'description': description,
            'color': color
        }]
    }
    # Use all valid tokens concurrently for sending with rate limit handling
    results = []
    def send_with_token(token):
        headers_send = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Add random headers to bypass rate limit
        headers_send['X-Super-Properties'] = 'eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJyZWxlYXNlX2NoYW5uZWwiOiJzdGFibGUiLCJjbGllbnRfdmVyc2lvbiI6IjEuMC45MDAxIiwib3NfdmVyc2lvbiI6IjEwLjAuMTkwNDIiLCJvc192ZXJzIjoiV2luZG93cyAxMCBEdWJpb24ifQ=='
        headers_send['X-Fingerprint'] = ''.join(random.choices('0123456789abcdef', k=32))
        max_retries = 5
        backoff = 1
        for attempt in range(max_retries):
            response = requests.post(url, headers=headers_send, data=json.dumps(data))
            if response.status_code == 200:
                results.append(True)
                break
            elif response.status_code == 429:
                retry_after = response.headers.get('Retry-After', str(backoff))
                time.sleep(int(retry_after) + backoff)
                backoff *= 2
            else:
                break  # Other errors, don't retry
    threads = []
    for token in valid_tokens:
        t = threading.Thread(target=send_with_token, args=(token,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return results if results else False

def react_to_message(channel_id, message_id, emoji):
    emoji_encoded = urllib.parse.quote(emoji)
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}/reactions/{emoji_encoded}/@me'
    response = requests.put(url, headers=headers)
    return response.status_code == 204

def delete_message(channel_id, message_id):
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}'
    # Use all valid tokens concurrently for deleting
    results = []
    def delete_with_token(token):
        headers_delete = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.delete(url, headers=headers_delete)
        if response.status_code == 204:
            results.append(True)
    threads = []
    for token in valid_tokens:
        t = threading.Thread(target=delete_with_token, args=(token,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return results if results else False

def edit_message(channel_id, message_id, new_content):
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}'
    data = {'content': new_content}
    response = requests.patch(url, headers=headers, data=json.dumps(data))
    return response.status_code == 200

def get_recent_messages(channel_id, limit=10):
    messages = []
    before = None
    while len(messages) < limit:
        batch_limit = min(100, limit - len(messages))
        url = f'https://discord.com/api/v9/channels/{channel_id}/messages?limit={batch_limit}'
        if before:
            url += f'&before={before}'
        max_retries = 5  # Increased retries for SSL issues
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    batch = response.json()
                    if not batch:
                        return messages
                    messages.extend(batch)
                    before = batch[-1]['id']
                    break
                elif response.status_code == 403:
                    return messages
                elif response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', 1)
                    time.sleep(int(retry_after) + 1)
                else:
                    return messages
            except requests.exceptions.SSLError as e:
                print(Fore.YELLOW + f"SSL Error on attempt {attempt + 1}: {e}. Retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
            except requests.exceptions.RequestException as e:
                print(Fore.YELLOW + f"Request Error on attempt {attempt + 1}: {e}. Retrying...")
                time.sleep(2 ** attempt)
        else:
            print(Fore.RED + f"Failed to fetch messages after {max_retries} attempts.")
            return messages
    return messages[:limit]

def get_user_info(user_id):
    url = f'https://discord.com/api/v9/users/{user_id}'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def get_server_info(guild_id):
    url = f'https://discord.com/api/v9/guilds/{guild_id}'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def get_guild_from_channel(channel_id):
    url = f'https://discord.com/api/v9/channels/{channel_id}'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('guild_id')
    return None

def get_channel_id_by_name(guild_id, channel_name):
    if not guild_id:
        return None
    url = f'https://discord.com/api/v9/guilds/{guild_id}/channels'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        channels = response.json()
        for ch in channels:
            if ch['name'] == channel_name and ch['type'] == 0:  # text channel
                return ch['id']
    return None

def change_status(status_text):
    url = 'https://discord.com/api/v9/users/@me/settings'
    data = {'custom_status': {'text': status_text}}
    response = requests.patch(url, headers=headers, data=json.dumps(data))
    return response.status_code == 200

def join_voice_channel(channel_id):
    global current_voice_guild
    guild_id = get_guild_from_channel(channel_id)
    if not guild_id:
        print(Fore.RED + "Invalid voice channel ID.")
        return
    url = f'https://discord.com/api/v9/channels/{channel_id}'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        ch = response.json()
        if ch['type'] != 2:  # 2 is voice channel
            print(Fore.RED + "Not a voice channel.")
            return
    else:
        print(Fore.RED + "Failed to get channel info.")
        return
    # Note: Actual voice joining requires gateway connection, this is a placeholder
    print(Fore.GREEN + f"Joined voice channel {channel_id} in guild {guild_id}")
    current_voice_guild = guild_id

def leave_voice_channel():
    global current_voice_guild
    if current_voice_guild:
        print(Fore.GREEN + f"Left voice channel in guild {current_voice_guild}")
        current_voice_guild = None
    else:
        print(Fore.YELLOW + "Not in a voice channel.")

def autoping_function(user_id, interval):
    global autoping_active, autoping_channel
    while autoping_active:
        if autoping_channel:
            send_message(autoping_channel, f'<@{user_id}>')
        time.sleep(interval)

def chatpack_function(user_id):
    global chatpack_active, chatpack_channel
    messages = ['Hello :)', 'How are you niggah', 'i like your girl friend ', 'i love your mom', 'BRB', 'GG', 'shut up bobo', 'Nice', 'Thanks', 'Bye','Fuck you nigga','Oh what do you say bich']
    while chatpack_active:
        if chatpack_channel:
            send_message(chatpack_channel, f'<@{user_id}> {random.choice(messages)}')
        time.sleep(5)

def process_command(content, channel_id, message_id, from_console=False):
    global autoping_active, autoping_thread, chatpack_active, chatpack_thread

    parts = content.split()
    cmd = parts[0][1:]  # Remove ,
    print(f"-- {cmd}")

    if cmd == 'cmds':
        embed_desc = """
• drage
**Owners**
-** i lost my soul ** // discord server infinity invite url

dsc.gg/jUfY2zNdkF

- Developer and Owner : drage_gg
---------------------------------------
**Reaction**
- react <channel_id> <user_id> <emoji>
- stop <channel_id> <user_id>
- clear <channel_id>

**Messaging**
- spam <channel_id> <msg> <count>
- chatpack <channel_id> <user>
- massdm <msg> or <filename>
- say <channel_id> <msg>
- embed <channel_id> <title> | <desc>
- dm <user_id> <msg>
- loop <channel_id> <msg> <count> <delay>
- type <channel_id> <msg>
- emoji <channel_id> <emoji>

**Control**
- edit <channel_id> <msg_id> <new>
- end <channel_id>
- delete <channel_id> <msg_id>
- purge <channel_id> <amount>
- copy <channel_id> <msg_id>
- vanish <channel_id>
- invite <invite_code>
- join <voice_channel_id>

**Logs & Auto**
- removereply <channel_id> <trigger>
- showlogs <channel_id>

**Utilities**
- autoping <channel_id> <user_id> <interval>
- stopautoping
- status <text>
- ping <channel_id>
- userinfo <channel_id> <user_id>
- serverinfo <channel_id>
- cloak <new_name>
- hack <channel_id> <user>
- guildcopy <source_guild_id> <target_guild_id>
- nuke <guild_id> <msg> <count>
------------------------------------------------------
        """
        if from_console:
            print(embed_desc)
        else:
            send_message(channel_id, f"```{embed_desc}```")

    elif cmd == 'spam':
        if len(parts) < 4:
            if from_console:
                print('Usage: ,spam <#channel_name or channel_id> <msg> <count>')
            else:
                send_message(channel_id, 'Usage: ,spam <#channel_name or channel_id> <msg> <count>')
            return
        target_input = parts[1]
        if target_input.startswith('#'):
            channel_name = target_input[1:]
            guild_id = get_guild_from_channel(channel_id)
            target_channel = get_channel_id_by_name(guild_id, channel_name)
            if not target_channel:
                if from_console:
                    print(f'Channel #{channel_name} not found in this server.')
                else:
                    send_message(channel_id, f'Channel #{channel_name} not found in this server.')
                return
        else:
            target_channel = target_input
        msg = ' '.join(parts[2:-1])
        count = int(parts[-1])
        
        max_workers = multiprocessing.cpu_count() * 2
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(count):
                
                random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=random.randint(1,5)))
                modified_msg = f"{msg} {random_suffix}" if random.random() > 0.5 else msg
                futures.append(executor.submit(send_message, target_channel, modified_msg))
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(Fore.RED + f"Error sending message: {e}")

    elif cmd == 'say':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,say <#channel_name or channel_id> <msg>')
            else:
                send_message(channel_id, 'Usage: ,say <#channel_name or channel_id> <msg>')
            return
        target_input = parts[1]
        if target_input.startswith('#'):
            channel_name = target_input[1:]
            guild_id = get_guild_from_channel(channel_id)
            target_channel = get_channel_id_by_name(guild_id, channel_name)
            if not target_channel:
                if from_console:
                    print(f'Channel #{channel_name} not found in this server.')
                else:
                    send_message(channel_id, f'Channel #{channel_name} not found in this server.')
                return
        else:
            target_channel = target_input
        msg = ' '.join(parts[2:])
        send_message(target_channel, msg)

    elif cmd == 'embed':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,embed <channel_id> <title> | <desc>')
            else:
                send_message(channel_id, 'Usage: ,embed <channel_id> <title> | <desc>')
            return
        target_channel = parts[1]
        title_desc = ' '.join(parts[2:]).split(' | ')
        title = title_desc[0]
        desc = title_desc[1] if len(title_desc) > 1 else ''
        send_embed(target_channel, title, desc)

    elif cmd == 'dm':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,dm <user_id> <msg>')
            else:
                send_message(channel_id, 'Usage: ,dm <user_id> <msg>')
            return
        dm_user = parts[1]
        dm_msg = ' '.join(parts[2:])
        dm_channel = create_dm(dm_user)
        if dm_channel:
            send_message(dm_channel, dm_msg)

    elif cmd == 'delete':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,delete <channel_id> <msg_id>')
            else:
                send_message(channel_id, 'Usage: ,delete <channel_id> <msg_id>')
            return
        target_channel = parts[1]
        delete_message(target_channel, parts[2])

    elif cmd == 'edit':
        if len(parts) < 4:
            if from_console:
                print('Usage: ,edit <channel_id> <msg_id> <new>')
            else:
                send_message(channel_id, 'Usage: ,edit <channel_id> <msg_id> <new>')
            return
        target_channel = parts[1]
        edit_message(target_channel, parts[2], ' '.join(parts[3:]))

    elif cmd == 'purge':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,purge <#channel_name or channel_id> <amount>')
            else:
                send_message(channel_id, 'Usage: ,purge <#channel_name or channel_id> <amount>')
            return
        target_input = parts[1]
        if target_input.startswith('#'):
            channel_name = target_input[1:]
            guild_id = get_guild_from_channel(channel_id)
            target_channel = get_channel_id_by_name(guild_id, channel_name)
            if not target_channel:
                if from_console:
                    print(f'Channel #{channel_name} not found in this server.')
                else:
                    send_message(channel_id, f'Channel #{channel_name} not found in this server.')
                return
        else:
            target_channel = target_input
        amount = int(parts[2])
        
        messages = get_recent_messages(target_channel, min(amount * 2, 1000))  
        selfbot_messages = [msg for msg in messages if msg['author']['id'] in user_ids]
        
        def delete_msg(msg):
            delete_message(target_channel, msg['id'])
        threads = []
        for msg in selfbot_messages[:amount]:
            t = threading.Thread(target=delete_msg, args=(msg,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    elif cmd == 'react':
        if len(parts) < 4:
            if from_console:
                print('Usage: ,react <channel_id> <user_id> <emoji>')
            else:
                send_message(channel_id, 'Usage: ,react <channel_id> <user_id> <emoji>')
            return
        target_channel = parts[1]
        target_user = parts[2]
        emoji = ' '.join(parts[3:])
       
        messages = get_recent_messages(target_channel, limit=50)
        user_message = None
        for msg in messages:
            if msg['author']['id'] == target_user:
                user_message = msg
                break
        if user_message:
            success = react_to_message(target_channel, user_message['id'], emoji)
            if not success:
                if from_console:
                    print('Failed to react to the message.')
                else:
                    send_message(channel_id, 'Failed to react to the message.')
        else:
            if from_console:
                print('No recent message found from that user.')
            else:
                send_message(channel_id, 'No recent message found from that user.')

    elif cmd == 'autoping':
        if len(parts) < 4:
            if from_console:
                print('Usage: ,autoping <channel_id> <user_id> <interval>')
            else:
                send_message(channel_id, 'Usage: ,autoping <channel_id> <user_id> <interval>')
            return
        target_channel = parts[1]
        ping_user = parts[2]
        interval = int(parts[3])
        autoping_active = True
        autoping_channel = target_channel
        autoping_thread = threading.Thread(target=autoping_function, args=(ping_user, interval))
        autoping_thread.start()

    elif cmd == 'stopautoping':
        autoping_active = False
        if autoping_thread:
            autoping_thread.join()

    elif cmd == 'chatpack':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,chatpack <channel_id> <user_id>')
            else:
                send_message(channel_id, 'Usage: ,chatpack <channel_id> <user_id>')
            return
        target_channel = parts[1]
        chat_user = parts[2]
        chatpack_active = True
        chatpack_channel = target_channel
        chatpack_thread = threading.Thread(target=chatpack_function, args=(chat_user,))
        chatpack_thread.start()

    elif cmd == 'stopchatpack':
        chatpack_active = False
        if chatpack_thread:
            chatpack_thread.join()

    elif cmd == 'status':
        if len(parts) < 2:
            if from_console:
                print('Usage: ,status <text>')
            else:
                send_message(channel_id, 'Usage: ,status <text>')
            return
        change_status(' '.join(parts[1:]))

    elif cmd == 'ping':
        if len(parts) < 2:
            if from_console:
                print('Usage: ,ping <channel_id>')
            else:
                send_message(channel_id, 'Usage: ,ping <channel_id>')
            return
        target_channel = parts[1]
        send_message(target_channel, 'Pong!')

    elif cmd == 'userinfo':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,userinfo <channel_id> <user_id>')
            else:
                send_message(channel_id, 'Usage: ,userinfo <channel_id> <user_id>')
            return
        target_channel = parts[1]
        target_user = parts[2]
        info = get_user_info(target_user)
        if info:
            send_embed(target_channel, f"User Info: {info['username']}", f"ID: {info['id']}\nDiscriminator: {info['discriminator']}")

    elif cmd == 'serverinfo':
        if len(parts) < 2:
            if from_console:
                print('Usage: ,serverinfo <channel_id>')
            else:
                send_message(channel_id, 'Usage: ,serverinfo <channel_id>')
            return
        target_channel = parts[1]
        guild_id = get_guild_from_channel(target_channel)
        if guild_id:
            info = get_server_info(guild_id)
            if info:
                member_count = info.get('member_count', 'N/A')
                send_embed(target_channel, f"Server Info: {info['name']}", f"ID: {info['id']}\nMember Count: {member_count}")
        else:
            send_message(target_channel, 'Not in a server.')

    elif cmd == 'invite':
        if len(parts) < 2:
            if from_console:
                print('Usage: ,invite <invite_code>')
            else:
                send_message(channel_id, 'Usage: ,invite <invite_code>')
            return
        invite_code = parts[1]
        
        if 'discord.gg/' in invite_code:
            invite_code = invite_code.split('discord.gg/')[-1]
        for token in valid_tokens:
            join_server(token, invite_code)
        if from_console:
            print('Invitation processes completed.')
        else:
            send_message(channel_id, 'Invitation processes completed.')

    elif cmd == 'join':
        if len(parts) < 2:
            print('Usage: ,join <voice_channel_id>')
            return
        voice_id = parts[1]
        join_voice_channel(voice_id)

    elif cmd == 'unjoin':
        leave_voice_channel()

    elif cmd == 'guildcopy':
        if len(parts) < 3:
            if from_console:
                print('Usage: ,guildcopy <source_guild_id> <target_guild_id>')
            else:
                send_message(channel_id, 'Usage: ,guildcopy <source_guild_id> <target_guild_id>')
            return
        source_guild = parts[1]
        target_guild = parts[2]

        
        if not from_console:
            send_message(channel_id, 'Starting guild copy process...')

        
        url_roles = f'https://discord.com/api/v9/guilds/{source_guild}/roles'
        response = requests.get(url_roles, headers=headers)
        if response.status_code != 200:
            error_msg = f'Failed to fetch roles from source guild: {response.status_code}'
            if from_console:
                print(error_msg)
            else:
                send_message(channel_id, error_msg)
            return
        source_roles = response.json()
        role_mapping = {}  

        
        for role in source_roles:
            if role['name'] == '@everyone':
                role_mapping[role['id']] = role['id']  # @everyone is always the same
                continue
            url_create_role = f'https://discord.com/api/v9/guilds/{target_guild}/roles'
            role_data = {
                'name': role['name'],
                'permissions': role['permissions'],
                'color': role['color'],
                'hoist': role['hoist'],
                'mentionable': role['mentionable']
            }
            max_retries = 5
            backoff = 1
            for attempt in range(max_retries):
                response = requests.post(url_create_role, headers=headers, data=json.dumps(role_data))
                if response.status_code == 201:
                    new_role = response.json()
                    role_mapping[role['id']] = new_role['id']
                    break
                elif response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', str(backoff))
                    time.sleep(float(retry_after) if retry_after else backoff)
                    backoff *= 2
                else:
                    break
            if response.status_code != 201:
                error_msg = f'Failed to create role {role["name"]}: {response.status_code}'
                if from_console:
                    print(error_msg)
                else:
                    send_message(channel_id, error_msg)

        
        if not from_console:
            send_message(channel_id, 'Roles copied. Copying categories...')

        
        url_channels = f'https://discord.com/api/v9/guilds/{source_guild}/channels'
        response = requests.get(url_channels, headers=headers)
        if response.status_code != 200:
            error_msg = f'Failed to fetch channels from source guild: {response.status_code}'
            if from_console:
                print(error_msg)
            else:
                send_message(channel_id, error_msg)
            return
        source_channels = response.json()
        category_mapping = {}  

        
        categories = [ch for ch in source_channels if ch['type'] == 4]
        other_channels = [ch for ch in source_channels if ch['type'] in [0, 2]]  # text and voice

        # Create categories in target guild
        for cat in categories:
            url_create_channel = f'https://discord.com/api/v9/guilds/{target_guild}/channels'
            cat_data = {
                'name': cat['name'],
                'type': 4
            }
            max_retries = 5
            backoff = 1
            for attempt in range(max_retries):
                response = requests.post(url_create_channel, headers=headers, data=json.dumps(cat_data))
                if response.status_code == 201:
                    new_cat = response.json()
                    category_mapping[cat['id']] = new_cat['id']
                    break
                elif response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', str(backoff))
                    time.sleep(float(retry_after) if retry_after else backoff)
                    backoff *= 2
                else:
                    break
            if response.status_code != 201:
                error_msg = f'Failed to create category {cat["name"]}: {response.status_code}'
                if from_console:
                    print(error_msg)
                else:
                    send_message(channel_id, error_msg)

        # Progress message
        if not from_console:
            send_message(channel_id, 'Categories copied. Copying channels...')

        # Create other channels in target guild
        for ch in other_channels:
            url_create_channel = f'https://discord.com/api/v9/guilds/{target_guild}/channels'
            ch_data = {
                'name': ch['name'],
                'type': ch['type'],
                'topic': ch.get('topic', ''),
                'nsfw': ch.get('nsfw', False),
                'bitrate': ch.get('bitrate', 64000),
                'user_limit': ch.get('user_limit', 0),
                'rate_limit_per_user': ch.get('rate_limit_per_user', 0)
            }
            if ch.get('parent_id') and ch['parent_id'] in category_mapping:
                ch_data['parent_id'] = category_mapping[ch['parent_id']]

            # Copy permission overwrites
            if 'permission_overwrites' in ch:
                overwrites = []
                for ow in ch['permission_overwrites']:
                    if ow['id'] in role_mapping:
                        overwrites.append({
                            'id': role_mapping[ow['id']],
                            'type': ow['type'],
                            'allow': ow['allow'],
                            'deny': ow['deny']
                        })
                if overwrites:
                    ch_data['permission_overwrites'] = overwrites

            max_retries = 5
            backoff = 1
            for attempt in range(max_retries):
                response = requests.post(url_create_channel, headers=headers, data=json.dumps(ch_data))
                if response.status_code == 201:
                    break
                elif response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', str(backoff))
                    time.sleep(float(retry_after) if retry_after else backoff)
                    backoff *= 2
                else:
                    break
            if response.status_code != 201:
                error_msg = f'Failed to create channel {ch["name"]}: {response.status_code}'
                if from_console:
                    print(error_msg)
                else:
                    send_message(channel_id, error_msg)

        # Final message
        if not from_console:
            send_message(channel_id, 'Guild copy completed!')

    elif cmd == 'nuke':
        if len(parts) < 4:
            if from_console:
                print('Usage: ,nuke <guild_id> <msg> <count>')
            else:
                send_message(channel_id, 'Usage: ,nuke <guild_id> <msg> <count>')
            return
        guild_id = parts[1]
        msg = ' '.join(parts[2:-1])
        try:
            count = int(parts[-1])
        except ValueError:
            if from_console:
                print('Count must be an integer.')
            else:
                send_message(channel_id, 'Count must be an integer.')
            return
        # Fetch channels from the specified guild
        url_channels = f'https://discord.com/api/v9/guilds/{guild_id}/channels'
        response_channels = requests.get(url_channels, headers=headers)
        if response_channels.status_code != 200:
            error_msg = f'Failed to get channels for guild {guild_id}: {response_channels.status_code}'
            if from_console:
                print(error_msg)
            else:
                send_message(channel_id, error_msg)
            return
        channels = response_channels.json()
        all_text_channels = [ch for ch in channels if ch['type'] in [0, 5]]  # text and announcement channels
        if not all_text_channels:
            error_msg = f'No writable channels found in guild {guild_id}.'
            if from_console:
                print(error_msg)
            else:
                send_message(channel_id, error_msg)
            return
        # Send 'count' messages to each channel sequentially, starting from the first channel
        for ch in all_text_channels:
            for _ in range(count):
                send_message(ch['id'], msg)
                # Add a small random delay to bypass rate limits
                time.sleep(random.uniform(0.1, 0.5))

    # Add more commands as needed

def create_dm(user_id):
    url = 'https://discord.com/api/v9/users/@me/channels'
    data = {'recipient_id': user_id}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        return response.json()['id']
    return None

def join_server(token, invite_code):
    headers_join = {
        'Authorization': token,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    url = f'https://discord.com/api/v9/invites/{invite_code}'
    response = requests.post(url, headers=headers_join)
    if response.status_code == 200:
        print(f"Token {token[:10]}... sunucuya katıldı.")
        return True
    else:
        print(f"Token {token[:10]}... katılmadı: {response.status_code} - {response.text}")
        return False



def check_channel(ch_id):
    global command_processed
    try:
        messages = get_recent_messages(ch_id, limit=5)
        for msg in messages:
            if ch_id not in last_message_ids or int(msg['id']) > int(last_message_ids[ch_id]):
                if msg['author']['id'] in owners and msg['id'] not in processed_messages:
                    content = msg['content']
                    if content.startswith(','):
                        process_command(content, ch_id, msg['id'])
                        processed_messages.add(msg['id'])
                        active_channels.add(ch_id)
                        command_processed = True
        if messages:
            last_message_ids[ch_id] = messages[0]['id']
    except Exception as e:
        print(Fore.RED + f"Error checking channel {ch_id}: {e}")

def channel_scan_loop():
    global running, last_refresh, all_channels
    while running:
        if time.time() - last_refresh > 300:
            all_channels = get_all_channels()
            last_refresh = time.time()
        try:
            # Scan channels concurrently for faster detection
            threads = []
            for ch_id in all_channels:
                t = threading.Thread(target=check_channel, args=(ch_id,))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            time.sleep(0.0001)  # Further reduced delay for faster scanning
        except Exception as e:
            print(Fore.RED + f"Hata: {e}")
            time.sleep(1)  # Shorter error delay

def console_loop():
    global running
    while running:
        try:
            cmd = input(Fore.GREEN + "> " + Style.RESET_ALL)
            if cmd.strip():
                process_command(cmd, None, None, from_console=True)
        except KeyboardInterrupt:
            running = False
        except EOFError:
            running = False



# Ana döngü
if __name__ == '__main__':
    os.system("clear")
    os.system("cls")
    print(Fore.RED + """
_______________________________________________________
       ░██                                             |
       ░██                                             |
 ░████████ ░██░████  ░██████    ░████████  ░███████    |
░██    ░██ ░███           ░██  ░██    ░██ ░██    ░██   |
░██    ░██ ░██       ░███████  ░██    ░██ ░█████████   |
░██   ░███ ░██      ░██   ░██  ░██   ░███ ░██          |
 ░█████░██ ░██       ░█████░██  ░█████░██  ░███████    |
                                      ░██              |
                                ░███████               |
_______________________________________________________|
""")
    print(Fore.LIGHTBLACK_EX + "")
    print(Fore.LIGHTGREEN_EX + "Selfbot by drage_gg")
    print(Fore.LIGHTRED_EX + "dsc: https://discord.gg/jUfY2zNdkF")

    # Get all accessible channels
    all_channels = get_all_channels()
    if not all_channels:
        print(Fore.RED + "No channels found automatically. Skipping channel scanning.")
        all_channels = []  # Empty list to avoid errors
    last_refresh = time.time()

    # Initialize last_message_ids with the latest message ID for each channel
    for ch_id in all_channels:
        messages = get_recent_messages(ch_id, limit=1)
        if messages:
            last_message_ids[ch_id] = messages[0]['id']

    # Start channel scanning thread if channels exist
    if all_channels:
        scan_thread = threading.Thread(target=channel_scan_loop)
        scan_thread.start()

    # Start console thread for command input
    console_thread = threading.Thread(target=console_loop)
    console_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        autoping_active = False
        chatpack_active = False
        if all_channels:
            scan_thread.join()
        console_thread.join()
        print(Fore.RED + "Exiting...")
