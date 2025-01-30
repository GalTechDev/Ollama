import discord
import requests
from understar.system import lib
import json
import traceback
import base64

Lib = lib.App()

url = "http://localhost:11434/api/chat"

template = "Context, tu es un bot discord Francais.\n\n"

data = {
    "model": "llama3.2-vision",
    "messages": [],
    "keep_alive": -1,
    "stream": True
}

historiques = {}

def ask_ia(ask, user_id, contents):
    
    if user_id not in list(historiques.keys()):
        historiques[user_id] = []
                
    historiques[user_id].append({"role": "user", "content": ask, "images":contents})

    temp_data = data.copy()
    temp_data["messages"] = historiques[user_id]

    
    resp = ""
    for token in send_prompt(temp_data):
        resp+=token
        yield token

    historiques[user_id].append({"role": "assistant", "content": resp})
    return resp

def send_prompt(json_data):
    
    try:

        with requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(json_data),
            stream=True  # Activer le mode streaming
        ) as response:
            # Vérifier le statut de la réponse
            if response.status_code == 200:

                # Lire la réponse au fur et à mesure
                for chunk in response.iter_lines(decode_unicode=True):
                    if chunk:
                        chunk_data = json.loads(chunk)  # Charger chaque ligne JSON
                        token = chunk_data.get("message", {}).get("content")
                        yield token

            else:
                print("Erreur lors de la requête :", response.status_code, response.text)
    except Exception as e:
        print("Erreur :", e)


async def ask_ia_command(ctx, words: str, contents: list):
    try:
        if isinstance(words, str):
            message = words

        text = ""
        last_block = ""
        response = None
        for t in ask_ia(message, ctx.author.id, contents):
            try:
                last_block += t
            
                if len(last_block) > 40:
                    if response:
                        new_block = ""
                        if "\n\n" in last_block:
                            if (text+last_block.split("\n\n")[1]).count("```")%2==0:
                                new_block = last_block.split("\n\n")[1]

                                last_block = last_block.split("\n\n")[0]
                                if new_block == "":
                                    new_block = "\n"

                        text += last_block
                        last_block = new_block

                        text_send = str(text[:2000])
                        
                        if new_block:
                            await response.edit(content=text_send)
                            response = None
                            text = ""
                        else:
                            text_send = str(text[:1999]+"⌷")
                            await response.edit(content=text_send)
                    else:
                        text_send = str(text[:1999]+"⌷")

                        response = await ctx.channel.send(content=text_send)
            except TypeError as e:
                print(traceback.format_exc())
        text+=last_block
        await response.edit(content=text[:2000])
    except Exception as e:
        print(type(e), e)

@Lib.event.event()
async def on_message(message: discord.message.Message):
    if message.author.id == Lib.client.user.id:
        return
    
    if message.content[:5] == "?ask ":
        words = message.content[5:]
        try:
            contents = []
            for content in message.attachments:
                if content.content_type in ('image/jpeg', 'image/jpg', 'image/png') and not content.is_voice_message():
                    contents.append(base64.b64encode(await content.read()).decode())
        except Exception as e:
            print(e)

        await ask_ia_command(message, words, contents)

    if message.content[:8] == "?forget ":
        if message.author.id in historiques:
            historiques.pop(message.author.id)
        


    if message.reference and not message.is_system():
        user_id = message.reference.resolved.author.id
        if user_id == Lib.client.user.id:
            try:
                text = ""
                last_block = ""
                response = None
                for t in ask_ia(response, message.author.id):
                    last_block += t
                    if len(last_block) > 20:
                        text += last_block
                        last_block = ""
                        if response:
                            await response.edit(content=text[:1999]+"⌷")
                        else:
                            response = await message.channel.send(text[:1999]+"⌷")
                text+=last_block
                await response.edit(content=text[:2000])
            except Exception as e:
                print(e)

