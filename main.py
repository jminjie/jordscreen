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
from PIL import ExifTags

AUTO_UPDATE_AT_CYCLE_END = True
TIME_PER_IMAGE_IN_SECONDS = 10
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

def get_updated_messages(service):
    results = service.users().messages().list(
            userId='me', q='label:jordscreen').execute()
    return results.get('messages', [])

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
    image = Image.open(BytesIO(base64.urlsafe_b64decode(b64)))
    for orientation in ExifTags.TAGS.keys():
        if ExifTags.TAGS[orientation]=='Orientation':
            break
    exif = image._getexif()
    if exif is None:
        print("no exif")
        return image

    if exif[orientation] == 3:
        print("rotating 1")
        image=image.rotate(180, expand=True)
    elif exif[orientation] == 6:
        print("rotating 2")
        image=image.rotate(270, expand=True)
    elif exif[orientation] == 8:
        print("rotating 3")
        image=image.rotate(90, expand=True)

    return image


def resize_image(pilImage, w, h):
    imgWidth, imgHeight = pilImage.size
    if imgWidth > w or imgHeight > h:
        ratio = min(w/imgWidth, h/imgHeight)
        imgWidth = int(imgWidth*ratio)
        imgHeight = int(imgHeight*ratio)
        pilImage = pilImage.resize((imgWidth,imgHeight), Image.ANTIALIAS)
    return pilImage

def show_next_image(service, messages, root, canvas, w, h, cur_message, image_container):
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
        global current_image
        current_image = ImageTk.PhotoImage(resize_image(pilImage, w, h))
        canvas.itemconfig(image_container, image=current_image)

def on_button_press():
    print("WE PRESSED THE BUTTON WOOHOO")

def auto_update_image(service, messages, root, canvas, w, h, cur_message, image_container):
    cur_message += 1
    if cur_message is len(messages):
        if AUTO_UPDATE_AT_CYCLE_END:
            messages = get_updated_messages()
        cur_message = 0

    show_next_image(service, messages, root, canvas, w, h, cur_message, image_container)
    root.after(3000, auto_update_image, service, messages, root, canvas, w, h,
            cur_message, image_container)

current_image = None

def main():
    service = get_service()
    messages = get_updated_messages(service)
    create_cache_dir()

    if not messages:
        print("No messages. Quitting.")
        return

    root = tkinter.Tk()
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.overrideredirect(1)
    root.geometry("%dx%d+0+0" % (w, h))
    root.focus_set()

    button = tkinter.Button(root, text="Press me", command=on_button_press)
    button.pack()

    canvas = tkinter.Canvas(root, width=w, height=h)
    canvas.pack()
    canvas.configure(background='black')

    cur_message = 0
    message = messages[cur_message]
    msg_id = message['id']
    print("msg_id =", msg_id)
    msg = get_message_from_id(service, msg_id)
    attachment_id = get_attachment_id_for_simple_msg(msg)

    image_container = None
    if attachment_id is not None:
        print("attachment_id = ", attachment_id)
        attachment = get_attachment_from_id(service, msg_id, attachment_id)
        #TODO only if im is an image type
        pilImage = get_image_from_base64url(attachment)
        global current_image
        current_image = ImageTk.PhotoImage(resize_image(pilImage, w, h))
        image_container = canvas.create_image(w/2, h/2, image=current_image)

    root.after(3000, auto_update_image, service, messages, root, canvas, w, h,
            cur_message, image_container)
    root.mainloop()

if __name__ == '__main__':
    main()
