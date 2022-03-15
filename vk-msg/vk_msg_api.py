import random
import requests
import time
import json
from difflib import SequenceMatcher

class Exception_MessagesAPI(Exception):

    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = f'MessagesAPIexception[{errors}]'

class MessagesAPI:

    def __init__(self, login, password, debug):

        self.debug = debug
        self.login = login
        self.password = str(password.encode('UTF-8')).replace('\\x', '%')[2:-1]

        # здесь используються client_id и client_secret из декомпилированного андройд приложения
        # получаем access_token для дальнейшей работы
        response = requests.get(f'https://oauth.vk.com/token?grant_type=password&client_id=2274003&client_secret=hHbZxrka2uZ6jB1inYsH&username={self.login}&password={self.password}')
        response_json = json.loads(response.text)

        if 'error' in response_json.keys():
            if self.debug == True:
                print(r"Debug | Access Token: ", response_json)
            if 'error' in response_json.keys():
                raise Exception_MessagesAPI(response_json, response_json['error'])

        self.access_token = response_json['access_token']


    def method(self, name, **kwargs):

        params = ''
        for i in kwargs:
            params+=f'{i}={kwargs[i]}&'
        response = requests.get(f'https://api.vk.com/method/{name}?access_token={self.access_token}&{params}v=5.131')
        response_json = json.loads(response.text)

        if 'error' in response_json.keys():
            if self.debug == True:
                print(r"Debug | Method: ", response_json)
            raise Exception_MessagesAPI(response_json['error']['error_msg'],
                                        response_json['error']['error_code'])
        return response_json['response']

class Longpool:

    def __init__(self, debug=False, ConnectionErrorMax=0, WaitTime=0.3):
        self.debug = debug
        self.ConnectionErrorMax = ConnectionErrorMax
        self.ConnectionErrorCount = 1
        self.WaitTime = WaitTime

    def get_start_pts(self, login, password):
        while True:
            time.sleep(self.WaitTime)
            try:
                vk_user = MessagesAPI(login=login, password=password, debug = self.debug)
                pts = vk_user.method('messages.getLongPollServer', need_pts=1)['pts']
                if self.debug == True:
                    print(r"Debug | Start Pts: ", pts)
                break

            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Start Pts: ConnectionError", self.ConnectionErrorCount)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(r"Debug | Start Pts: ConnectionError: Exceeded the number of connection errors when trying to get starting pts")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get starting pts")
                else:
                    self.ConnectionErrorCount+=1
                    continue

        self.ConnectionErrorCount = 0
        return pts, vk_user

    def get_pool(self, pts, vk_user):

        while True:
            try:
                time.sleep(self.WaitTime)
                event = vk_user.method('messages.getLongPollHistory', pts=pts)
                if event['from_pts'] == event['new_pts']:
                    self.ConnectionErrorCount = 0
                    continue
                elif event['from_pts'] < event['new_pts']:
                    if self.debug == True:
                        print(r"Debug | Pool: ", event)
                    self.ConnectionErrorCount = 0
                    return event
                else:
                    self.ConnectionErrorCount = 0
                    continue


            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Pool: ConnectionError", self.ConnectionErrorCount, "/", self.ConnectionErrorMax)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(
                            r"Debug | Start Pts: ConnectionError: Exceeded the number of connection errors when trying to get pool")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get pool")
                else:
                    self.ConnectionErrorCount += 1
                    continue

class Actions:

    def __init__(self, self_vk_id,  debug=False):
        self.debug = debug
        self.vk_id = self_vk_id

    def get_msgs(self, pool):
        events = []
        conversations = {}
        for items in pool['conversations']:
            admins = []
            if 'chat_settings' in items:
                admins.append(items['chat_settings']['owner_id'])
                items['chat_settings'].setdefault('admin_ids', [])
                admins.extend(items['chat_settings']['admin_ids'])
                conversations[items['peer']['id']] = admins
            else:
                conversations[items['peer']['id']] = [0]
        for items in pool['messages']['items']:
            items.setdefault('deleted', 0)
            if items['deleted'] == 0:
                if items['fwd_messages'] == []:
                    if items.setdefault("reply_message", []) == []:
                        fwd_rep_id = False
                    else:
                        fwd_rep_id = items["reply_message"]['from_id']
                else:
                    fwd_rep_id = items["fwd_messages"][0]['from_id']
                if self.vk_id in conversations[items['peer_id']]:
                    isHasPrim = True
                else:
                    isHasPrim = False
                if items['from_id'] in conversations[items['peer_id']]:
                    isAdmin = True
                else:
                    isAdmin = False
                events.append(
                    {'isHasPrim': isHasPrim, 'text': items['text'], 'peer_id': items['peer_id'], 'from_id': items['from_id'], 'id': items['id'], 'isAdmin': isAdmin, 'fwd_rep_id': fwd_rep_id})
        if self.debug == True:
            print(r"Debug | Msgs: ", events)
        return events

    def compare_text(self, text_1, text_2: list, accuracy=0.75):
        for items in text_2:
            precision = SequenceMatcher(lambda x: x == " ", text_1.lower(), items.lower()).ratio()
            if self.debug == True:
                print(r"Debug | СompareT: ", precision, "/", accuracy,'\t\t', text_1, ' |' , items, sep="")
            if precision >= accuracy:
                return True
        return False

    def compare_word(self, text_1, text_2: list, accuracy=0.75):
        for word in text_1.split():
            for items in text_2:
                precision = SequenceMatcher(lambda x: x == " ", word.lower(), items.lower()).ratio()
                if self.debug == True:
                    print(r"Debug | СompareW: ", precision, "/", accuracy,'\t\t', word, ' |' , items, sep="")
                if precision >= accuracy:
                    return True
        return False

    def compare_first_word(self, text_1, text_2: list, accuracy=0.75):
        if len(text_1) > 0:
            word = text_1.split()[0]
        else:
            if self.debug == True:
                print(r"Debug | СompareF: Haven't any word")
            return False
        for items in text_2:
            precision = SequenceMatcher(lambda x: x == " ", word.lower(), items.lower()).ratio()
            if self.debug == True:
                print(r"Debug | СompareF: ", precision, "/", accuracy,'\t\t', word, ' |' , items, sep="")
            if precision >= accuracy:
                return True
        return False

class Method:

    def __init__(self, vk_user, debug=False, ConnectionErrorMax=0, WaitTime=0.3, setActivity=True):
        self.vk_user = vk_user
        self.debug = debug
        self.ConnectionErrorMax = ConnectionErrorMax
        self.WaitTime = WaitTime
        self.setActivity = setActivity
        self.ConnectionErrorCount = 1

    def send_msg(self, text, peer_id):
        while True:
            try:
                if self.setActivity == True:
                    self.set_activity(peer_id=peer_id)
                time.sleep(self.WaitTime)
                return self.vk_user.method('messages.send', random_id=random.randint(1, 2147483647), peer_id=peer_id,
                               message=text)
            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Send: ConnectionError", self.ConnectionErrorCount, "/", self.ConnectionErrorMax)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(
                            r"Debug | Send: ConnectionError: Exceeded the number of connection errors when trying to get pool")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get pool")
                else:
                    self.ConnectionErrorCount += 1
                    continue

    def delete_msg(self, message_ids, delete_for_all=True):
        while True:
            try:
                time.sleep(self.WaitTime)
                response = self.vk_user.method('messages.delete',message_ids=",".join(str(x) for x in message_ids), delete_for_all=delete_for_all)
                if self.debug == True:
                    print(r"Debug | Delete:", response)
                return response
            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Delete: ConnectionError", self.ConnectionErrorCount, "/", self.ConnectionErrorMax)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(
                            r"Debug | Delete: ConnectionError: Exceeded the number of connection errors when trying to get pool")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get pool")
                else:
                    self.ConnectionErrorCount += 1
                    continue

    def set_activity(self, peer_id, type='typing'):
        while True:
            try:
                time.sleep(self.WaitTime)
                return self.vk_user.method('messages.setActivity', type='typing', peer_id=peer_id)
            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Activity: ConnectionError", self.ConnectionErrorCount, "/", self.ConnectionErrorMax)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(
                            r"Debug | Activity: ConnectionError: Exceeded the number of connection errors when trying to get pool")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get pool")
                else:
                    self.ConnectionErrorCount += 1
                    continue

    def get_comments(self, group_id, topic_id, count, offset):
        while True:
            try:
                time.sleep(self.WaitTime)
                return self.vk_user.method('board.getComments', group_id=group_id, topic_id=topic_id, count=count, offset=offset)
            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Comments: ConnectionError", self.ConnectionErrorCount, "/", self.ConnectionErrorMax)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(
                            r"Debug | Comments: ConnectionError: Exceeded the number of connection errors when trying to get pool")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get pool")
                else:
                    self.ConnectionErrorCount += 1
                    continue

    def remove_user(self, user_id, peer_id):
        while True:
            try:
                time.sleep(self.WaitTime)
                return self.vk_user.method('messages.removeChatUser', user_id=user_id, chat_id=peer_id-2000000000)
            except requests.exceptions.ConnectionError:
                if self.debug == True:
                    print(r"Debug | Remove: ConnectionError", self.ConnectionErrorCount, "/", self.ConnectionErrorMax)
                if self.ConnectionErrorCount >= self.ConnectionErrorMax:
                    if self.debug == True:
                        print(
                            r"Debug | Remove: ConnectionError: Exceeded the number of connection errors when trying to get pool")
                    raise ConnectionError("Exceeded the number of connection errors when trying to get pool")
                else:
                    self.ConnectionErrorCount += 1
                    continue

class Bot:

    def __init__(self, vk_user, debug=False):
        self.debug = debug
        self.vk_user = vk_user

    def run(self, messeges: list, dict: dict, accuracy=0.95):
        del_msg=[]
        for msg in messeges:
            for key in dict:
                precision = SequenceMatcher(lambda x: x == " ", msg['text'].lower(), key.lower()).ratio()
                if self.debug == True:
                    print("Debug | Сompare: ", precision, "/", accuracy, '\t\t', msg['text'], '|', key, sep="")
                if precision >= accuracy:
                    if dict[key][0] == "send":
                        Method(self.vk_user, self.debug).send_msg(dict[key][1], msg['peer_id'])
                    elif dict[key][0] == "delete" and msg["isHasPrim"] == True and msg["isAdmin"] == False:
                        del_msg.append(msg["id"])
        if del_msg != []:
            Method(self.vk_user, self.debug).delete_msg(",".join(str(x) for x in del_msg))
        return False


