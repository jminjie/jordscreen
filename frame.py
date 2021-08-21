import os.path
import base64
import tkinter
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from PIL import Image
from io import BytesIO
from PIL import ImageTk

AUTO_UPDATE_AT_CYCLE_END = True
TIME_PER_IMAGE_IN_SECONDS = 60
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

def get_message_from_id(service, id):
    # makes a request to get the message
    return service.users().messages().get(userId='me', id=id).execute()

def create_cache_dir():
    if not os.path.exists('cache'):
        os.mkdir('cache')

def get_attachment_id_for_simple_msg(msg):
    try:
        return msg['payload']['parts'][1]['body']['attachmentId']
    except KeyError:
        print("No attachment in msg id =", msg['id'])
        return None

def get_attachment_from_id(service, msg_id, attachment_id):
    file_path = 'cache/' + msg_id
    if os.path.exists(file_path):
        print("cache hit!")
        with open(file_path) as reader:
            return reader.read()
    else:
        print("cache miss, downloading attachment")
        attachment = service.users().messages().attachments().get(userId='me',
                messageId=msg_id, id=attachment_id).execute()
        with open(file_path, 'w') as writer:
            writer.write(attachment['data'])
        return attachment['data']

def get_image_from_base64url(b64):
    # base64url is slighly different from base64
    return Image.open(BytesIO(base64.urlsafe_b64decode(b64)))

def resize_image(pilImage, w, h):
    imgWidth, imgHeight = pilImage.size
    if imgWidth > w or imgHeight > h:
        ratio = min(w/imgWidth, h/imgHeight)
        imgWidth = int(imgWidth*ratio)
        imgHeight = int(imgHeight*ratio)
        pilImage = pilImage.resize((imgWidth,imgHeight), Image.ANTIALIAS)
    return pilImage


def show_next_image(service, messages, root, canvas, w, h, cur_message):
    message = messages[cur_message]
    msg_id = message['id']
    print("msg_id =", msg_id)
    msg = get_message_from_id(service, msg_id)

    attachment_id = get_attachment_id_for_simple_msg(msg)

    if attachment_id is not None:
        print("attachment_id = ", attachment_id)
        attachment = get_attachment_from_id(service, msg_id, attachment_id)
        #TODO only if im is an image type
        pilImage = get_image_from_base64url(attachment)
        image = ImageTk.PhotoImage(resize_image(pilImage, w, h))
        imagesprite = canvas.create_image(w/2,h/2,image=image)
        root.update_idletasks()
        root.update()



def main():
    service = get_service()
    results = service.users().messages().list(
            userId='me', q='label:jordscreen').execute()
    messages = results.get('messages', [])

    create_cache_dir()

    if not messages:
        print("No messages found.")
    else:
        print("Message attachments:")
        root = tkinter.Tk()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.overrideredirect(1)
        root.geometry("%dx%d+0+0" % (w, h))
        root.focus_set()
        canvas = tkinter.Canvas(root,width=w,height=h)
        canvas.pack()
        canvas.configure(background='black')

        cur_message = 0
        while True:
            show_next_image(service, messages, root, canvas, w, h, cur_message)
            time.sleep(TIME_PER_IMAGE_IN_SECONDS)
            cur_message = cur_message + 1
            if cur_message is len(messages):
                cur_message = 0
                if AUTO_UPDATE_AT_CYCLE_END:
                    results = service.users().messages().list(
                            userId='me', q='label:jordscreen').execute()
                    messages = results.get('messages', [])



if __name__ == '__main__':
    main()
