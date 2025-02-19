import asyncio
import random
import ssl
import json
import time
import uuid
import base64
import aiohttp
import requests
from datetime import datetime
from colorama import init, Fore, Style
from websockets_proxy import Proxy, proxy_connect


init(autoreset=True)

BANNER = """

        (   (                                                        (            (   (     
        )\ ))\ )                        )                     (      )\ )   (     )\ ))\ )  
 (   ( (()/(()/(            (        ( /(        (    )       )\ )  (()/(   )\   (()/(()/(  
 )\  )\ /(_)/(_))  `  )   ( )\  (    )\())(     ))\  (     ( (()/(   /(_)((((_)(  /(_)/(_)) 
((_)((_(_))(_))    /(/(   )((_) )\ )(_))/ )\ ) /((_) )\  ' )\ /(_))_(_))  )\ _ )\(_))(_))   
\ \ / /|_ _| _ \  ((_)_\ ((_(_)_(_/(| |_ _(_/((_)) _((_)) ((_(_)) __| _ \ (_)_\(_/ __/ __|  
 \ V /  | ||  _/  | '_ \/ _ | | ' \)|  _| ' \)/ -_| '  \(/ _ \ | (_ |   /  / _ \ \__ \__ \  
  \_/  |___|_|    | .__/\___|_|_||_| \__|_||_|\___|_|_|_|\___/  \___|_|_\ /_/ \_\|___|___/  
                  |_|                                                                       
"""

async def fetch_user_agents():
    """Fetch latest user agents from GitHub"""
    url = "https://gist.githubusercontent.com/pzb/b4b6f57144aea7827ae4/raw/cf847b76a142955b1410c8bcef3aabe221a63db1/user-agents.txt"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text.splitlines()
    except Exception as e:
        print(f"{Fore.RED}Failed to fetch user agents: {e}{Style.RESET_ALL}")
        return []

# Initialize user agents
EDGE_USERAGENTS = asyncio.run(fetch_user_agents())


HTTP_STATUS_CODES = {
    200: "OK",
    201: "Created", 
    202: "Accepted",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden", 
    404: "Not Found",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout"
}

def colorful_log(proxy, device_id, message_type, message_content, is_sent=False, mode=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    color = Fore.GREEN if is_sent else Fore.BLUE
    action_color = Fore.YELLOW
    mode_color = Fore.LIGHTYELLOW_EX
    
    log_message = (
        f"{Fore.WHITE}[{timestamp}] "
        f"{Fore.MAGENTA}[Proxy: {proxy}] "
        f"{Fore.CYAN}[Device ID: {device_id}] "
        f"{action_color}[{message_type}] "
        f"{color}{message_content} "
        f"{mode_color}[{mode}]"
    )
    
    print(log_message)

async def connect_to_wss(socks5_proxy, user_id, mode):
    device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socks5_proxy))
    
    random_user_agent = random.choice(EDGE_USERAGENTS)
    
    colorful_log(
        proxy=socks5_proxy,  
        device_id=device_id, 
        message_type="INITIALIZATION", 
        message_content=f"User Agent: {random_user_agent}",
        mode=mode
    )

    has_received_action = False
    is_authenticated = False
    
    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {
                "User-Agent": random_user_agent,
                "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi" if mode == "extension" else None
            }
            custom_headers = {k: v for k, v in custom_headers.items() if v is not None}
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            urilist = [
                #"wss://proxy.wynd.network:4444/",
                #"wss://proxy.wynd.network:4650/",
                "wss://proxy2.wynd.network:4444/",
                "wss://proxy2.wynd.network:4650/",
                #"wss://proxy3.wynd.network:4444/",
                #"wss://proxy3.wynd.network:4650/"
            ]
            uri = random.choice(urilist)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        if has_received_action:
                            send_message = json.dumps(
                                {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, socks5_proxy)), 
                                 "version": "1.0.0", 
                                 "action": "PING", 
                                 "data": {}})
                            
                            colorful_log(
                                proxy=socks5_proxy,  
                                device_id=device_id, 
                                message_type="SENDING PING", 
                                message_content=send_message,
                                is_sent=True,
                                mode=mode
                            )
                            
                            await websocket.send(send_message)
                        await asyncio.sleep(5)

                await asyncio.sleep(1)
                ping_task = asyncio.create_task(send_ping())

                while True:
                    if is_authenticated and not has_received_action:
                        colorful_log(
                            proxy=socks5_proxy,
                            device_id=device_id,
                            message_type="AUTHENTICATED | WAIT UNTIL THE PING GATE OPENS",
                            message_content="Waiting for " + ("HTTP_REQUEST" if mode == "extension" else "OPEN_TUNNEL"),
                            mode=mode
                        )
                    
                    response = await websocket.recv()
                    message = json.loads(response)
                    
                    colorful_log(
                        proxy=socks5_proxy, 
                        device_id=device_id, 
                        message_type="RECEIVED", 
                        message_content=json.dumps(message),
                        mode=mode
                    )

                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": random_user_agent,
                                "timestamp": int(time.time()),
                                "device_type": "extension" if mode == "extension" else "desktop",
                                "version": "4.26.2" if mode == "extension" else "4.30.0"
                            }
                        }
                        
                        if mode == "extension":
                            auth_response["result"]["extension_id"] = "lkbnfiajjmbhnfledhphioinpickokdi"
                        
                        colorful_log(
                            proxy=socks5_proxy,  
                            device_id=device_id, 
                            message_type="AUTHENTICATING", 
                            message_content=json.dumps(auth_response),
                            is_sent=True,
                            mode=mode
                        )
                        
                        await websocket.send(json.dumps(auth_response))
                        is_authenticated = True
                    
                    elif message.get("action") in ["HTTP_REQUEST", "OPEN_TUNNEL"]:
                        has_received_action = True
                        request_data = message["data"]
                        
                        headers = {
                            "User-Agent": custom_headers["User-Agent"],
                            "Content-Type": "application/json; charset=utf-8"
                        }
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(request_data["url"], headers=headers) as api_response:
                                content = await api_response.text()
                                encoded_body = base64.b64encode(content.encode()).decode()
                                
                                status_text = HTTP_STATUS_CODES.get(api_response.status, "")
                                
                                http_response = {
                                    "id": message["id"],
                                    "origin_action": message["action"],
                                    "result": {
                                        "url": request_data["url"],
                                        "status": api_response.status,
                                        "status_text": status_text,
                                        "headers": dict(api_response.headers),
                                        "body": encoded_body
                                    }
                                }
                                
                                colorful_log(
                                    proxy=socks5_proxy,
                                    device_id=device_id,
                                    message_type="OPENING PING ACCESS",
                                    message_content=json.dumps(http_response),
                                    is_sent=True,
                                    mode=mode
                                )
                                
                                await websocket.send(json.dumps(http_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        
                        colorful_log(
                            proxy=socks5_proxy, 
                            device_id=device_id, 
                            message_type="SENDING PONG", 
                            message_content=json.dumps(pong_response),
                            is_sent=True,
                            mode=mode
                        )
                        
                        await websocket.send(json.dumps(pong_response))
                        
        except Exception as e:
            colorful_log(
                proxy=socks5_proxy, 
                device_id=device_id, 
                message_type="ERROR", 
                message_content=str(e),
                mode=mode
            )
            await asyncio.sleep(5)

async def fetch_proxies():
    """Fetch HTTP, SOCKS4 and SOCKS5 proxies from GitHub and return valid ones"""
    proxy_sources = {
        "http": "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/http.txt",
        "socks4": "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/socks4.txt",
        "socks5": "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/socks5.txt"
    }
    
    all_proxies = []
    for proxy_type, url in proxy_sources.items():
        try:
            response = requests.get(url)
            response.raise_for_status()
            proxies = response.text.splitlines()
            # Add proper prefix for each proxy type
            if proxy_type == "http":
                proxies = [f"http://{proxy}" for proxy in proxies]
            elif proxy_type == "socks4":
                proxies = [f"socks4://{proxy}" for proxy in proxies]
            elif proxy_type == "socks5":
                proxies = [f"socks5://{proxy}" for proxy in proxies]
            all_proxies.extend(proxies)
        except Exception as e:
            print(f"{Fore.RED}Failed to fetch {proxy_type} proxies: {e}{Style.RESET_ALL}")
    return all_proxies


async def validate_proxy(proxy):
    """Validate if a proxy is working"""
    try:
        # Handle different proxy types
        if proxy.startswith('http://'):
            proxy_url = proxy
        elif proxy.startswith('socks4://') or proxy.startswith('socks5://'):
            proxy_url = proxy
        else:
            proxy_url = f"http://{proxy}"
            
        async with aiohttp.ClientSession() as session:
            async with session.get('http://httpbin.org/ip', proxy=proxy_url, timeout=5) as response:
                if response.status == 200:
                    return True
    except Exception as e:
        print(f"{Fore.YELLOW}Proxy {proxy} failed: {e}{Style.RESET_ALL}")
    return False


async def filter_proxies(proxies):
    """Filter and return only working proxies"""
    tasks = [validate_proxy(proxy) for proxy in proxies]
    results = await asyncio.gather(*tasks)
    return [proxy for proxy, is_valid in zip(proxies, results) if is_valid]

async def update_proxies_periodically(interval=300):
    """Periodically update proxies while program is running"""
    while True:
        try:
            print(f"{Fore.YELLOW}Checking for proxy updates...{Style.RESET_ALL}")
            proxies = await fetch_proxies()
            valid_proxies = await filter_proxies(proxies)
            with open('proxy_list.txt', 'w') as f:
                f.write('\n'.join(f"http://{proxy}" if not proxy.startswith('http://') else proxy for proxy in valid_proxies))
            print(f"{Fore.GREEN}Proxy list updated. Valid proxies: {len(valid_proxies)}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Failed to update proxies: {e}{Style.RESET_ALL}")
        await asyncio.sleep(interval)

async def main():
    print(f"{Fore.CYAN}{BANNER}{Style.RESET_ALL}")
    print(f"{Fore.CYAN} Pointnemo | VIP PointnemoGRASS {Style.RESET_ALL}")
    
    # Start proxy update task
    update_task = asyncio.create_task(update_proxies_periodically())

    
    # Fetch and filter proxies
    print(f"{Fore.YELLOW}Fetching proxies from GitHub...{Style.RESET_ALL}")
    proxies = await fetch_proxies()
    print(f"{Fore.YELLOW}Found {len(proxies)} proxies. Validating...{Style.RESET_ALL}")
    valid_proxies = await filter_proxies(proxies)
    print(f"{Fore.GREEN}Valid proxies found: {len(valid_proxies)}{Style.RESET_ALL}")
    
    # Save valid proxies to file with http:// prefix
    with open('proxy_list.txt', 'w') as f:
        f.write('\n'.join(f"http://{proxy}" if not proxy.startswith('http://') else proxy for proxy in valid_proxies))

    
    print(f"{Fore.GREEN}Select Mode:{Style.RESET_ALL}")
    print("1. Extension Mode")
    print("2. Desktop Mode")
    
    while True:
        mode_choice = input("Enter your choice (1/2): ").strip()
        if mode_choice in ['1', '2']:
            break
        print(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")
    
    mode = "extension" if mode_choice == "1" else "desktop"
    print(f"{Fore.GREEN}Selected mode: {mode}{Style.RESET_ALL}")
    
    # Read user ID from file or prompt if not found
    try:
        with open('user_id.txt', 'r') as f:
            _user_id = f.read().strip()
            if not _user_id:
                raise FileNotFoundError
        print(f"{Fore.GREEN}Using user ID from user_id.txt{Style.RESET_ALL}")
    except FileNotFoundError:
        _user_id = input('Please Enter your user ID: ')
        with open('user_id.txt', 'w') as f:
            f.write(_user_id)

    
    with open('proxy_list.txt', 'r') as file:
        local_proxies = file.read().splitlines()
    
    print(f"{Fore.YELLOW}Total Proxies: {len(local_proxies)}{Style.RESET_ALL}")
    
    tasks = [asyncio.ensure_future(connect_to_wss(i, _user_id, mode)) for i in local_proxies]
    await asyncio.gather(*tasks, update_task)


if __name__ == '__main__':
    asyncio.run(main())
