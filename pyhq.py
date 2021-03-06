import json
import requests
import re
import datetime
import os
import time

apiUrl = "https://api-quiz.hype.space"

_first_re = re.compile("(.)([A-Z][a-z]+)")
_cap_re = re.compile("([a-z0-9])([A-Z])")
def _to_snake(name):
    s1 = _first_re.sub(r"\1_\2", name)
    return _cap_re.sub(r"\1_\2", s1).lower()


class HQUserLeaderboard:
    def __init__(self, **kwargs):
        self.total_cents = kwargs.get("total_cents")
        self.total = kwargs.get("total")
        self.unclaimed = kwargs.get("unclaimed")
        for p in ("alltime", "weekly"):
            for v in ("wins", "total", "rank"):
                try:
                    setattr(self, f"{p}_{v}", kwargs.get(p).get(v))
                except:
                    pass


class HQUserInfo:
    def __init__(self, **kwargs):
        self.user_id = kwargs.get("user_id")
        self.username = kwargs.get("username")
        self.avatar_url = kwargs.get("avatar_url")
        self.created_timestamp = kwargs.get("created_timestamp")
        self.broadcasts = kwargs.get("broadcasts")  # unused
        self.featured = kwargs.get("featured")  # unused
        self.referral_url = kwargs.get("referral_url")  # property?
        self.high_score = kwargs.get("high_score")
        self.games_played = kwargs.get("games_played")
        self.win_count = kwargs.get("win_count") # different than leaderboard.alltime_wins cuz i dont know, i think this is the accurate one
        self.blocked = kwargs.get("blocked")
        self.blocks_me = kwargs.get("blocks_me")
        try:
            x = kwargs.get("leaderboard")
            if isinstance(x, dict):
                kwargs2 = {}
                for k, v in x.items():
                    kwargs2[_to_snake(k)] = v
                self.leaderboard = HQUserLeaderboard(**kwargs2)
            elif isinstance(x, HQUserLeaderboard):
                self.leaderboard = x
        except Exception as e:
            raise e


class HQMeInfo(HQUserInfo):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.friend_ids = kwargs.get("friend_ids")
        self.stk = kwargs.get("stk")  # unused?
        self.voip = kwargs.get("voip")
        self.device_tokens = kwargs.get("device_tokens")
        self.preferences = kwargs.get("preferences")
        self.lives = kwargs.get("lives")
        self.phone_number = kwargs.get("phone_number")
        self.referred = kwargs.get("referred")


class HQClient:
    def __init__(self, login_token: str, client: str="iOS/1.3.28 b122", user_agent: str="HQ-iOS/122 CFNetwork/975.0.3 Darwin/18.2.0", caching=False, cache_time=15, no_ws_requests=False):
        self.login_token = login_token
        self.headers = {
            "x-hq-client": client,
            "user-agent": user_agent
        }
        self.auth_token = self.get_auth_token()
        self.ws = None
        self.ws_on_message = lambda x: None
        self.ws_on_error = lambda x: None
        self.ws_on_close = lambda x: None
        self.caching = caching  # probably could just decorate but im too lazy
        self.cache_time = cache_time
        self._cache = {}
        self.no_ws_requests = no_ws_requests

    def get_auth_token(self) -> str:
        return requests.post(f"{apiUrl}/tokens/", headers=self.headers, json={'token': self.login_token}).json()['authToken']

    @property
    def default_headers(self) -> dict:
        return {
            "x-hq-client": self.headers["x-hq-client"],
            "authorization": "Bearer " + self.auth_token,
            "user-agent": self.headers["user-agent"]
        }

    def valid_auth(self) -> bool:
        return "active" in self.schedule()

    def make_it_rain(self) -> bool:
        return requests.post(f"{apiUrl}/easter-eggs/makeItRain", headers=self.default_headers).status_code == 200

    def search_users(self, user: str) -> list:
        if self.caching:
            if "search_users" in self._cache:
                if user in self._cache["search_users"]:
                    if (time.time() - self._cache["search_users"][user]["last_update"]) < self.cache_time:
                        return self._cache["search_users"][user]["value"]
        response = requests.get(f"{apiUrl}/users?q=" + user, headers=self.default_headers)
        ret = []
        for x in response.json()["data"]:
            kwargs = {}
            for k, v in x.items():
                kwargs[_to_snake(k)] = v
            ret.append(HQUserInfo(**kwargs))
        if self.caching:
            if "search_users" not in self._cache:
                self._cache["search_users"] = {}
            self._cache["search_users"][user] = {
                "value": ret,
                "last_update": time.time()
            }
        return ret

    def user_info(self, something) -> HQUserInfo:
        if isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("User not found")
            else:
                user_id = search[0].user_id
        elif isinstance(something, int):
            user_id = something
        if self.caching:
            if "user_info" in self._cache:
                if user_id in self._cache["user_info"]:
                    if (time.time() - self._cache["user_info"][user_id]["last_update"]) < self.cache_time:
                        return self._cache["user_info"][user_id]["value"]
        response = requests.get(f"{apiUrl}/users/me", headers=self.default_headers)
        kwargs = {}
        for k, v in response.json().items():
            kwargs[_to_snake(k)] = v
        ret = HQUserInfo(**kwargs)
        if self.caching:
            if "user_info" not in self._cache:
                self._cache["user_info"] = {}
            self._cache["user_info"][user_id] = {
                "value": ret,
                "last_update": time.time()
            }
        return ret

    def me(self) -> HQMeInfo:
        response = requests.get(f"{apiUrl}/users/me", headers=self.default_headers)
        kwargs = {}
        for k, v in response.json().items():
            kwargs[_to_snake(k)] = v
        return HQMeInfo(**kwargs)

    def cashout(self, paypal: str) -> bool:
        return requests.post(f"{apiUrl}/users/me/payouts", headers=self.default_headers, json={"email": paypal}).status_code == 200

    def unlink(self) -> bool:
    	return requests.post(f"{apiUrl}/users/me/payouts/unlink", headers=self.default_headers).status_code == 200

    def addRefferal(self, refferal: str) -> bool:
        return requests.patch(f"{apiUrl}/users/me", headers=self.default_headers, json={"referringUsername": refferal}).status_code == 200

    def schedule(self) -> dict:
        if self.caching:
            if "schedule" in self._cache:
                if (time.time() - self._cache["schedule"]["last_update"]) < self.cache_time:
                    return self._cache["schedule"]["value"]
        ret = requests.get(f"{apiUrl}/shows/schedule?type=hq", headers=self.default_headers).json()
        if self.caching:
            if "schedule" not in self._cache:
                self._cache["schedule"] = {}
            self._cache["schedule"] = {
                "value": ret,
                "last_update": time.time()
            }
        return ret

    def aws_credentials(self) -> dict:
        return requests.get(f"{apiUrl}/credentials/s3", headers=self.default_headers).json()

    def delete_avatar(self) -> str:
        return requests.delete(f"{apiUrl}/users/me/avatarUrl", headers=self.default_headers).json()["avatarUrl"]

    def add_friend(self, something) -> dict:
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        elif isinstance(something, HQUserInfo):
            user_id = something.user_id
        response = requests.post(f"{apiUrl}/friends/{user_id}/requests", headers=self.default_headers).json()
        return {
            "requested_user": self.user_info(response["requestedUser"]["userId"]),
            "requesting_user": self.user_info(response["requestingUser"]["userId"]),
            "status": response["status"]
        }

    def friend_status(self, something):
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        return requests.get(f"{apiUrl}/friends/{user_id}/status", headers=self.default_headers).json()["status"]

    def accept_friend(self, something) -> dict:
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        response = requests.put(f"{apiUrl}/friends/{user_id}/status", headers=self.default_headers, json={
                "status": "ACCEPTED"
            }).json()
        return {
            "requested_user": self.user_info(response["requestedUser"]["userId"]),
            "requesting_user": self.user_info(response["requestingUser"]["userId"]),
            "status": response["status"],
            "accepted_timestamp": response["created"]  # milliseconds(?)
        }

    def remove_friend(self, something) -> bool:
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        return requests.delete(f"{apiUrl}/friends/{user_id}", headers=self.default_headers).json()["result"]

    def socket_url(self) -> str:
        if self.no_ws_requests:
            return "wss://hqecho.herokuapp.com/"  # tbh just replace the line its one method no args
        x = self.schedule()
        if x["shows"][0]["live"]:
            return x["shows"][0]["live"]["socketUrl"].replace("https", "wss")

    def generate_subscribe(self) -> str:
        if not self.no_ws_requests:
            x = self.schedule()
            broadcast_id = x["broadcast"]["broadcastId"]
        else:
            broadcast_id = "placeholder_broadcastid"
        return json.dumps({
            "type": "subscribe",
            "broadcastId": broadcast_id
        })

    def generate_answer(self, question_id: int, answer_id: int) -> str:
        if not self.no_ws_requests:
            x = self.schedule()
            broadcast_id = x["broadcast"]["broadcastId"]
        else:
            broadcast_id = "placeholder_broadcastid"

        return json.dumps({
            "type": "answer",
            "questionId": question_id,
            "broadcastId": broadcast_id,
            "answerId": answer_id
        })

    def generate_extra_life(self, question_id: int) -> str:
        if not self.no_ws_requests:
            x = self.schedule()
            broadcast_id = x["broadcast"]["broadcastId"]
        else:
            broadcast_id = "placeholder_broadcastid"

        return json.dumps({
            "type": "useExtraLife",
            "broadcastId": broadcast_id,
            "questionId": question_id
        })

def verify(phone: str) -> str:
    try:
        return requests.post(f"{apiUrl}/verifications", json={
            "method": "sms",
            "phone": phone
        }, headers={"x-hq-client": "Android/1.6.2", "user-agent": "okhttp/3.8.0"}).json()["verificationId"]
    except KeyError:
        raise Exception("invalid phone number")


def submit_code(verification_id: str, code: str) -> dict:
    return requests.post(f"{apiUrl}/verifications/" + verification_id, json={"code": code}).json()


def username_available(username: str) -> bool:
    return not bool(requests.post(f"{apiUrl}/usernames/available", json={"username": username}).json())


def create_user(username: str, verification_id: str, region: str="US", language: str="en"):
    return requests.post(f"{apiUrl}/users", json={
        "country": region,
        "language": language,
        "username": username,
        "verificationId": verification_id
    }).json()