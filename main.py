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
TIME_PER_IMAGE_IN_MS = 60 * 1000
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
        with open(file_path) as reader:
            return reader.read()
    else:
        print("Cache miss, downloading attachment")
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
        return image

    if orientation not in exif.keys():
        # handles KeyError 274
        print("Unexpected orientation =", orientation)
        return image

    if exif[orientation] == 3:
        image=image.rotate(180, expand=True)
    elif exif[orientation] == 6:
        image=image.rotate(270, expand=True)
    elif exif[orientation] == 8:
        image=image.rotate(90, expand=True)

    return image

def get_pil_image_from_id(service, msg_id):
    msg = get_message_from_id(service, msg_id)
    attachment_id = get_attachment_id_for_simple_msg(msg)

    if attachment_id is not None:
        attachment = get_attachment_from_id(service, msg_id, attachment_id)
        return get_image_from_base64url(attachment)
    else:
        print("Problem getting attachment attachment_id =", attachment_id)
        return None

class Display:
    def __init__(self, service, messages):
        self.service = service
        self.messages = messages

        self.root = tkinter.Tk()
        self.w, self.h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry("%dx%d+0+0" % (self.w, self.h))
        self.root.focus_set()
        self.root.focus()
        self.root.bind('<Escape>', self.close)
        self.root.attributes('-fullscreen', True)
        self.root.title('jordscreen')

        self.canvas = tkinter.Canvas(self.root, width=self.w, height=self.h, highlightthickness=0)
        self.canvas.place(x=0, y=0)
        self.canvas.configure(background='black')

        self.prev_button = tkinter.Button(self.root, text="Prev",
                command=self.go_to_previous_image)
        self.prev_button.pack(padx=30, ipadx=8, ipady=3, side = tkinter.LEFT)

        self.next_button = tkinter.Button(self.root, text="Next",
                command=self.go_to_next_image)
        self.next_button.pack(padx=30, ipadx=8, ipady=3, side = tkinter.RIGHT)

    def close(self, e):
        self.root.destroy()

    def set_current_image(self, pilImage):
        self.current_image = ImageTk.PhotoImage(self.resize_image(pilImage))
        self.image_container = self.canvas.create_image(self.w/2, self.h/2,
                image=self.current_image)

    def increment_cur_message(self):
        self.cur_message += 1
        if self.cur_message == len(self.messages):
            if AUTO_UPDATE_AT_CYCLE_END:
                self.messages = get_updated_messages(self.service)
            self.cur_message = 0

    def decrement_cur_message(self):
        self.cur_message -= 1
        if self.cur_message == -1:
            if AUTO_UPDATE_AT_CYCLE_END:
                self.messages = get_updated_messages(self.service)
            self.cur_message = len(self.messages) - 1

    def go_to_previous_image(self):
        self.root.after_cancel(self.after_id)

        self.decrement_cur_message()
        message = self.messages[self.cur_message]
        msg_id = message['id']
        msg = get_message_from_id(self.service, msg_id)
        attachment_id = get_attachment_id_for_simple_msg(msg)

        if attachment_id is not None:
            attachment = get_attachment_from_id(self.service, msg_id, attachment_id)
            #TODO check if this attachment is an image
            pilImage = get_image_from_base64url(attachment)
            self.set_current_image(pilImage)

        self.after_id = self.root.after(TIME_PER_IMAGE_IN_MS,
                self.auto_update_image, self.service, self.messages)

    def go_to_next_image(self):
        self.root.after_cancel(self.after_id)

        self.increment_cur_message()
        message = self.messages[self.cur_message]
        msg_id = message['id']
        msg = get_message_from_id(self.service, msg_id)
        attachment_id = get_attachment_id_for_simple_msg(msg)

        if attachment_id is not None:
            attachment = get_attachment_from_id(self.service, msg_id, attachment_id)
            #TODO check if this attachment is an image
            pilImage = get_image_from_base64url(attachment)
            self.set_current_image(pilImage)

        self.after_id = self.root.after(TIME_PER_IMAGE_IN_MS,
                self.auto_update_image, self.service, self.messages)


    def start(self):
        self.cur_message = 0

        # show first image
        message = self.messages[self.cur_message]
        msg_id = message['id']
        msg = get_message_from_id(self.service, msg_id)
        attachment_id = get_attachment_id_for_simple_msg(msg)

        if attachment_id is not None:
            attachment = get_attachment_from_id(self.service, msg_id, attachment_id)
            #TODO check if this attachment is an image
            pilImage = get_image_from_base64url(attachment)
            self.set_current_image(pilImage)

        # auto update image
        self.after_id = self.root.after(TIME_PER_IMAGE_IN_MS,
                self.auto_update_image, self.service, self.messages)
        self.root.mainloop()

    def resize_image(self, pilImage):
        imgWidth, imgHeight = pilImage.size
        if imgWidth > self.w or imgHeight > self.h:
            ratio = min(self.w/imgWidth, self.h/imgHeight)
            imgWidth = int(imgWidth*ratio)
            imgHeight = int(imgHeight*ratio)
            pilImage = pilImage.resize((imgWidth,imgHeight), Image.ANTIALIAS)
        return pilImage

    def auto_update_image(self, service, messages):
        self.increment_cur_message()

        message = messages[self.cur_message]
        msg_id = message['id']
        self.set_current_image(get_pil_image_from_id(service, msg_id))

        self.after_id = self.root.after(TIME_PER_IMAGE_IN_MS,
                self.auto_update_image, service, messages)

def main():
    service = get_service()
    messages = get_updated_messages(service)
    create_cache_dir()

    if not messages:
        print("No messages. Quitting.")
        return

    display = Display(service, messages)
    display.start()

if __name__ == '__main__':
    main()
