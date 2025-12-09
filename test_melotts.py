# from gradio_client import Client

# print("Connecting to MeloTTS Gradio interface...\n")

# try:
#     # Connect to the Gradio app
#     client = Client("http://localhost:8888/")
    
#     print("✓ Connected!")
#     print("\nTesting speech synthesis...\n")
    
#     # Call the synthesize function
#     # Based on the config: inputs are [text, speaker, speed, language]
#     result = client.predict(
#         "Hello world, this is a test!",  # text
#         "EN",                             # language
#         1.0,                              # speed  
#         "EN-US",                          # speaker
#         api_name="/synthesize"
#     )
    
#     print(f"✓ Success!")
#     print(f"Audio file saved at: {result}")
    
#     # The result should be a file path or URL to the generated audio
#     # You can now copy/download this file
    
# except Exception as e:
#     print(f"✗ Error: {e}")
#     print("\nTrying to get API info...")
    
#     try:
#         client = Client("http://localhost:8888/")
#         print("\nAvailable API endpoints:")
#         print(client.view_api())
#     except Exception as e2:
#         print(f"Could not get API info: {e2}")

