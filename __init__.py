import discord
import requests
from understar.system import lib
import json
import traceback
import base64
import logging

Lib = lib.App()

config = {}
protocol = "http"
domain = "localhost:11434"
model = "llama3.2-vision"

def data_load():
    global config, protocol, model, domain
    if not Lib.save.existe("config.json"):
        Lib.save.add_file("config.json")
        Lib.save.write("config.json", data="{}")

    config = Lib.save.json_read("config.json")
    protocol = config.get("protocol", protocol)
    config["protocol"] = protocol

    model = config.get("model", model)
    config["model"] = model

    domain = config.get("domain", domain)
    config["domain"] = domain

    Lib.save.write("config.json", data=json.dumps(config))

url = "{}://{}/api/chat"

template = "Context, tu es un bot discord Francais.\n\n"

data = {
    "model": "",
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
    temp_data["model"] = model
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
            url.format(protocol, domain),
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
                logging.error("Erreur lors de la requête :", response.status_code, response.text)
    except Exception as e:
        logging.error("Erreur :", e)


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
                logging.error(traceback.format_exc())
        text+=last_block
        await response.edit(content=text[:2000])
    except Exception as e:
        logging.error(f"{type(e)}, {e}")

async def updurl(ctx: discord.Interaction, new_domain, new_protocol):
    global domain, protocol
    domain = new_domain
    protocol = new_protocol

    config["domain"] = domain
    config["protocol"] = protocol

    Lib.save.write("config.json", data=json.dumps(config))

    await lib.valide_intaraction(ctx)


#############################################################
#                           Event                           #
#############################################################

@Lib.event.event()
async def on_ready():
    data_load()
    logging.info("Ollama ready !")


@Lib.event.event()
async def on_message(message: discord.message.Message):
    if message.author.id == Lib.client.user.id:
        return
    
    if message.content[:5] == "?ask ":
        words = message.content[5:]
        if len(words)==0:
            return
        try:
            contents = []
            for content in message.attachments:
                if content.content_type in ('image/jpeg', 'image/jpg', 'image/png') and not content.is_voice_message():
                    contents.append(base64.b64encode(await content.read()).decode())
        except Exception:
            logging.error(traceback.format_exc())

        await ask_ia_command(message, words, contents)

    if message.content == "?forget":
        try:
            if message.author.id in list(historiques.keys()):
                historiques.pop(message.author.id)
            logging.info(historiques)
        except Exception:
            logging.error(traceback.format_exc())
        


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
            except Exception:
                logging.error(traceback.format_exc())


#############################################################
#                           View                            #
#############################################################

class Updurl_view(discord.ui.View):
    def __init__(self, *, ctx: discord.Interaction, url="", _protocol="", timeout: lib.Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.url = url
        self._protocol = _protocol

        self.add_item(self.Url_button(view=self, label="Edit domaine" if self.url else "Set domaine", style=discord.ButtonStyle.green if self.url else discord.ButtonStyle.gray))
        self.add_item(self.Protocol_select(view=self, protocol=self._protocol, placeholder="Set protocol"))
        self.add_item(self.Valide_button(view=self, label="Validate", style=discord.ButtonStyle.blurple, disabled=(self.url=="" or self._protocol=="")))

    class Url_button(discord.ui.Button):
        def __init__(self, *, view, style: discord.ButtonStyle = discord.ButtonStyle.secondary, label: lib.Optional[str] = None, disabled: bool = False, custom_id: lib.Optional[str] = None, url: lib.Optional[str] = None, emoji: lib.Optional[lib.Union[str, discord.Emoji, discord.PartialEmoji]] = None, row: lib.Optional[int] = None):
            super().__init__(style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row)
            self.per_view = view

        async def callback(self, interaction: discord.Interaction) -> lib.Any:
            await interaction.response.send_modal(Updurl_modal(view=self.per_view, title="URL"))

    class Protocol_select(discord.ui.Select):
        def __init__(self, *, view, protocol, custom_id: str = lib.MISSING, placeholder: lib.Optional[str] = None, min_values: int = 1, max_values: int = 1, options: lib.List[discord.SelectOption] = lib.MISSING, disabled: bool = False, row: lib.Optional[int] = None) -> None:
            self.per_view = view
            self.keys = ["http", "https"]
            self.protocol = protocol
            options = [discord.SelectOption(label=key, default=True if self.protocol == key else False) for key in self.keys]
            super().__init__(custom_id=custom_id, placeholder=placeholder, min_values=min_values, max_values=max_values, options=options, disabled=disabled, row=row)

        async def callback(self, interaction: discord.Interaction) -> lib.Any:
            if self.values[0] in list(self.keys):
                await updurl_menu(self.per_view.ctx, self.per_view.url, self.values[0])
                await lib.valide_intaraction(interaction)

    class Valide_button(discord.ui.Button):
        def __init__(self, *, view, style: discord.ButtonStyle = discord.ButtonStyle.secondary, label: lib.Optional[str] = None, disabled: bool = False, custom_id: lib.Optional[str] = None, url: lib.Optional[str] = None, emoji: lib.Optional[lib.Union[str, discord.Emoji, discord.PartialEmoji]] = None, row: lib.Optional[int] = None):
            super().__init__(style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row)
            self.comfyui_domain = view.url
            self.per_view = view

        async def callback(self, interaction: discord.Interaction) -> lib.Any:
            await updurl(interaction, self.comfyui_domain, self.per_view._protocol)
            await config_menu(self.per_view.ctx)

class Config_view(discord.ui.View):
    def __init__(self, *, ctx: discord.Interaction, timeout: lib.Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.ctx=ctx

    @discord.ui.button(label="Edit URL",style=discord.ButtonStyle.gray)
    async def updurl_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        await updurl_menu(self.ctx)
        await lib.valide_intaraction(interaction)

#############################################################
#                          Modal                           #
#############################################################

class Updurl_modal(discord.ui.Modal):
    def __init__(self, *, view: Updurl_view, title: str = lib.MISSING, timeout: lib.Optional[float] = None, custom_id: str = lib.MISSING) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        self.url = discord.ui.TextInput(label="url", placeholder=domain)
        self.add_item(self.url)
        self.per_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        val = self.url.__str__()
        if not val:
            raise Exception()
        else:
            await updurl_menu(self.per_view.ctx, self.url.__str__(), self.per_view._protocol)
            await lib.valide_intaraction(interaction)


#############################################################
#                          Config                           #
#############################################################
async def updurl_menu(ctx: discord.Interaction, url="", _class=""):
    embed=discord.Embed(title=":gear:  Ollama Config")
    embed.description = "Update Ollama url"
    prot = _class
    
    await ctx.edit_original_response(embed=embed, view=Updurl_view(ctx=ctx, url=url, _protocol=prot))

@Lib.app.config()
async def config_menu(ctx: discord.Interaction):
    if not ctx.response.is_done():
        await ctx.response.send_message(embed=discord.Embed(title="Chargement..."), ephemeral=True)
    embed=discord.Embed(title=":gear:  Ollama Config")
    embed.add_field(name="Info :", value=f"Ollama URL : {protocol}://{domain}")
    embed.add_field(name="Info :", value=f"Workflow loaded : {1}")
    await ctx.edit_original_response(embed=embed, view=Config_view(ctx=ctx))