from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
import requests
import azure.cognitiveservices.speech as speechsdk
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT  = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
AGENT_ID          = os.environ.get("FOUNDRY_AGENT_ID")
FUNCTION_BASE_URL = os.environ.get("FUNCTION_BASE_URL")
FUNCTION_KEY      = os.environ.get("FUNCTION_KEY")
SPEECH_KEY        = os.environ.get("AZURE_SPEECH_KEY")
SPEECH_REGION     = os.environ.get("AZURE_SPEECH_REGION", "eastus")

VOICE_MAP = {
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-SoniaNeural",
    "es-MX": "es-MX-DaliaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "tl-PH": "fil-PH-BlessicaNeural",
    "ar-SA": "ar-SA-ZariyahNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural"
}

SUPPORTED_LANGUAGES = list(VOICE_MAP.keys())

agents_client = AgentsClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential()
)


def print_banner():
    print("\n" + "=" * 55)
    print("        RemitAI — Voice Remittance Agent")
    print("        Powered by Azure AI Foundry + USDC")
    print("=" * 55)
    print("Supported languages: English, Spanish, Hindi,")
    print("                     Tagalog, Arabic, French")
    print("Say 'quit' or 'exit' to stop")
    print("=" * 55 + "\n")


def get_voice_for_language(language_code: str) -> str:
    if language_code in VOICE_MAP:
        return VOICE_MAP[language_code]
    lang_prefix = language_code[:5] if len(language_code) >= 5 else language_code
    for key in VOICE_MAP:
        if key.startswith(lang_prefix[:2]):
            return VOICE_MAP[key]
    return VOICE_MAP["en-US"]


def speak(text: str, language: str = "en-US"):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=SPEECH_KEY,
            region=SPEECH_REGION
        )
        voice = get_voice_for_language(language)
        speech_config.speech_synthesis_voice_name = voice

        audio_config = speechsdk.audio.AudioOutputConfig(
            use_default_speaker=True
        )
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.Canceled:
            details = speechsdk.CancellationDetails(result)
            print(f"  [TTS error: {details.reason} — {details.error_details}]")

    except Exception as e:
        print(f"  [TTS failed: {str(e)}]")


def listen() -> tuple:
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=SPEECH_KEY,
            region=SPEECH_REGION
        )

        auto_detect = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
            languages=SUPPORTED_LANGUAGES
        )

        audio_config = speechsdk.audio.AudioConfig(
            use_default_microphone=True
        )

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            auto_detect_source_language_config=auto_detect,
            audio_config=audio_config
        )

        print("  Listening... (speak now)")
        result = recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            detected = result.properties.get(
                speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult,
                "en-US"
            )
            print(f"  You said [{detected}]: {result.text}")
            return result.text, detected

        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("  No speech detected")
            return None, "en-US"

        elif result.reason == speechsdk.ResultReason.Canceled:
            details = speechsdk.CancellationDetails(result)
            print(f"  [STT cancelled: {details.reason}]")
            print(f"  [Error code: {details.error_code}]")
            print(f"  [Error details: {details.error_details}]")
            return None, "en-US"

        return None, "en-US"

    except Exception as e:
        print(f"  [STT failed: {str(e)}]")
        return None, "en-US"


def call_function(name: str, arguments: dict) -> str:
    url     = f"{FUNCTION_BASE_URL}/{name}"
    headers = {
        "Content-Type":    "application/json",
        "x-functions-key": FUNCTION_KEY
    }
    try:
        response = requests.post(
            url,
            headers=headers,
            json=arguments,
            timeout=30
        )
        return json.dumps(response.json())
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_tool_calls(run, thread_id: str):
    if not run.required_action:
        return

    tool_outputs = []

    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        name      = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"\n  Calling: {name}")
        print(f"  Input:   {json.dumps(arguments, indent=2)}")

        result = call_function(name, arguments)

        try:
            parsed = json.loads(result)
            print(f"  Output:  {json.dumps(parsed, indent=2)[:300]}")
        except Exception:
            print(f"  Output:  {result[:300]}")

        tool_outputs.append({
            "tool_call_id": tool_call.id,
            "output":       result
        })

    agents_client.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run.id,
        tool_outputs=tool_outputs
    )


def send_message(user_text: str, thread_id: str) -> str:
    agents_client.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_text
    )

    run = agents_client.runs.create(
        thread_id=thread_id,
        agent_id=AGENT_ID
    )

    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = agents_client.runs.get(
            thread_id=thread_id,
            run_id=run.id
        )
        if run.status == "requires_action":
            handle_tool_calls(run, thread_id)

    if run.status == "failed":
        error = getattr(run, 'last_error', 'Unknown error')
        print(f"  [Run failed: {error}]")
        return "I'm sorry, something went wrong. Please try again."

    messages  = list(agents_client.messages.list(thread_id=thread_id))
    last_msg  = messages[0]
    response  = last_msg.content[0].text.value

    return response


def validate_config():
    missing = []
    if not PROJECT_ENDPOINT:
        missing.append("FOUNDRY_PROJECT_ENDPOINT")
    if not AGENT_ID:
        missing.append("FOUNDRY_AGENT_ID")
    if not FUNCTION_BASE_URL:
        missing.append("FUNCTION_BASE_URL")
    if not FUNCTION_KEY:
        missing.append("FUNCTION_KEY")
    if not SPEECH_KEY:
        missing.append("AZURE_SPEECH_KEY")

    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Please check your .env file")
        return False
    return True


def run_text_mode():
    print("\nRunning in TEXT mode (no microphone)")
    print("Type your messages below\n")

    thread    = agents_client.threads.create()
    thread_id = thread.id
    language  = "en-US"

    greeting = "Hello! I am RemitAI. I can help you send money home quickly and cheaply using stablecoins. How can I help you today?"
    print(f"\nRemitAI: {greeting}\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit"]:
            print("\nRemitAI: Thank you for using RemitAI. Goodbye!")
            break

        print("\nThinking...")
        response = send_message(user_input, thread_id)
        print(f"\nRemitAI: {response}\n")


def run_voice_mode():
    print("\nRunning in VOICE mode")
    print("Press Enter to speak, say 'quit' to exit\n")

    thread    = agents_client.threads.create()
    thread_id = thread.id
    language  = "en-US"

    greeting = "Hello! I am RemitAI. I can help you send money home quickly and cheaply. How can I help you today?"
    print(f"\nRemitAI: {greeting}")
    speak(greeting, language)

    while True:
        print("\n--- Press Enter to speak ---")
        input()

        spoken_text, detected_language = listen()

        if not spoken_text:
            msg = "Sorry I could not hear you. Please try again."
            print(f"\nRemitAI: {msg}")
            speak(msg, language)
            continue

        if spoken_text.lower().strip().rstrip(".") in ["quit", "exit"]:
            farewell = "Thank you for using RemitAI. Goodbye!"
            print(f"\nRemitAI: {farewell}")
            speak(farewell, language)
            break

        language = detected_language

        print("\nThinking...")
        response = send_message(spoken_text, thread_id)

        print(f"\nRemitAI: {response}")
        speak(response, language)


def main():
    print_banner()

    if not validate_config():
        return

    print("Select mode:")
    print("  1 — Voice mode (microphone + speakers)")
    print("  2 — Text mode (keyboard + terminal)")
    mode = input("\nEnter 1 or 2: ").strip()

    if mode == "1":
        run_voice_mode()
    else:
        run_text_mode()


if __name__ == "__main__":
    main()