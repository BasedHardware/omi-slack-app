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
        Scopes: channels:read, chat:write, users:read
        """
        scopes = "channels:read,chat:write,users:read,groups:read,im:read,mpim:read"
        auth_url = (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={self.client_id}&"
            f"scope={scopes}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )
        return auth_url
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        """
        Exchange authorization code for access token.
        Returns token data including access_token and team info.
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
                    return {
                        "access_token": data.get("access_token"),
                        "team_id": data.get("team", {}).get("id"),
                        "team_name": data.get("team", {}).get("name"),
                        "scope": data.get("scope")
                    }
                else:
                    raise Exception(f"Slack OAuth error: {data.get('error')}")
            else:
                raise Exception(f"Token exchange failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Token exchange error: {e}")
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
            print(f"❌ Error listing channels: {e.response['error']}")
            return []
        except Exception as e:
            print(f"❌ Error listing channels: {e}")
            return []
    
    async def send_message(
        self,
        access_token: str,
        channel_id: str,
        text: str
    ) -> Optional[dict]:
        """
        Send a message to a Slack channel.
        Returns message data if successful.
        """
        client = WebClient(token=access_token)
        
        try:
            result = client.chat_postMessage(
                channel=channel_id,
                text=text
            )
            
            if result.get("ok"):
                return {
                    "success": True,
                    "ts": result.get("ts"),
                    "channel": result.get("channel"),
                    "text": text
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }
                
        except SlackApiError as e:
            error_msg = e.response.get('error', str(e))
            print(f"❌ Slack API error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

