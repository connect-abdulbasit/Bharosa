from PIL import Image, ImageDraw
im = Image.new("RGB", (800, 500), (235, 240, 235)); d = ImageDraw.Draw(im)
d.rectangle([20, 20, 780, 480], outline=(30, 80, 60), width=6)
d.text((60, 60), "SAHARA DEMO ID CARD (SIMULATED)", fill=(20, 60, 40))
d.text((60, 140), "Name: Fatima Noor", fill=(0, 0, 0)); d.text((60, 190), "ID: 0000042101002", fill=(0, 0, 0))
im.save("id.jpg", quality=90)
