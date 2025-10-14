import os
import requests
from typing import Optional, List, Dict
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()


class SlackClient:
    """Handles Slack API interactions."""
    
    def __init__(self):
        self.client_id = os.getenv("SLACK_CLIENT_ID")
        self.client_secret = os.getenv("SLACK_CLIENT_SECRET")
    
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate Slack OAuth authorization URL.
        Uses USER token scopes so messages appear as sent by the user, not a bot.
        """
        # User token scopes (messages appear as the user)
        user_scopes = "channels:read,chat:write,groups:read,users:read"
        
        auth_url = (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={self.client_id}&"
            f"user_scope={user_scopes}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )
        return auth_url
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        """
        Exchange authorization code for access token.
        Returns USER token so messages appear as sent by the user, not a bot.
        """
        try:
            response = requests.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    print(f"🔍 OAuth Response Keys: {list(data.keys())}", flush=True)
                    
                    # Use the USER token (authed_user) instead of bot token
                    authed_user = data.get("authed_user", {})
                    user_token = authed_user.get("access_token")
                    
                    if not user_token:
                        # Fallback to bot token if user token not available
                        user_token = data.get("access_token")
                        print("⚠️  WARNING: Using BOT token (user token not available)", flush=True)
                        print(f"⚠️  This means messages will post as BOT, not as USER", flush=True)
                        print(f"⚠️  Check Slack app settings - ensure User Token Scopes are set", flush=True)
                    else:
                        print("✅ Using USER token (messages will appear as user)", flush=True)
                        print(f"✅ User token starts with: {user_token[:15]}...", flush=True)
                    
                    return {
                        "access_token": user_token,
                        "team_id": data.get("team", {}).get("id"),
                        "team_name": data.get("team", {}).get("name"),
                        "scope": data.get("scope"),
                        "token_type": "user" if user_token == authed_user.get("access_token") else "bot"
                    }
                else:
                    raise Exception(f"Slack OAuth error: {data.get('error')}")
            else:
                raise Exception(f"Token exchange failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Token exchange error: {e}", flush=True)
            raise
    
    def list_channels(self, access_token: str) -> List[Dict]:
        """
        List all channels the bot has access to (public channels, private groups, DMs).
        Returns list of {id, name, is_channel, is_group, is_im, is_private}
        """
        client = WebClient(token=access_token)
        channels = []
        
        try:
            # Get public channels
            result = client.conversations_list(
                types="public_channel,private_channel",
                exclude_archived=True,
                limit=200
            )
            
            for channel in result.get("channels", []):
                channels.append({
                    "id": channel["id"],
                    "name": channel["name"],
                    "is_channel": channel.get("is_channel", False),
                    "is_group": channel.get("is_group", False),
                    "is_private": channel.get("is_private", False),
                    "is_member": channel.get("is_member", False)
                })
            
            return channels
            
        except SlackApiError as e:
            print(f"❌ Error listing channels: {e.response['error']}", flush=True)
            return []
        except Exception as e:
            print(f"❌ Error listing channels: {e}", flush=True)
            return []
    
    async def send_message(
        self,
        access_token: str,
        channel_id: str,
        text: str
    ) -> Optional[dict]:
        """
        Send a message to a Slack channel as the authenticated user.
        With user tokens, messages automatically post as the user.
        Returns message data if successful.
        """
        client = WebClient(token=access_token)
        
        # Debug: Check token type
        token_prefix = access_token[:15] if access_token else "None"
        token_type = "USER" if access_token and access_token.startswith("xoxp-") else "BOT" if access_token and access_token.startswith("xoxb-") else "UNKNOWN"
        print(f"🔑 Sending with {token_type} token: {token_prefix}...", flush=True)
        
        try:
            # Note: as_user parameter is deprecated and not needed with user tokens
            # User tokens automatically post messages as the authenticated user
            result = client.chat_postMessage(
                channel=channel_id,
                text=text
            )
            
            if result.get("ok"):
                # Check if message was posted by bot or user
                message_data = result.get("message", {})
                subtype = message_data.get("subtype")
                bot_id = message_data.get("bot_id")
                username = message_data.get("username", "N/A")
                
                if bot_id:
                    print(f"⚠️  Message posted as BOT (bot_id: {bot_id})", flush=True)
                else:
                    print(f"✅ Message posted as USER", flush=True)
                
                return {
                    "success": True,
                    "ts": result.get("ts"),
                    "channel": result.get("channel"),
                    "text": text,
                    "posted_as": "bot" if bot_id else "user"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }
                
        except SlackApiError as e:
            error_msg = e.response.get('error', str(e))
            print(f"❌ Slack API error: {error_msg}", flush=True)
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            print(f"❌ Error sending message: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

