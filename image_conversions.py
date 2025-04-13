import base64
from io import BytesIO

from PIL import Image
from PyQt5.QtGui import QImage, QPixmap
from rdkit import Chem
from rdkit.Chem import Draw

from app_constants import *  # noqa


def pixmap_to_base64(pixmap):
    buffer = BytesIO()
    image = pixmap.toImage()
    ptr = image.bits()
    ptr.setsize(image.byteCount())
    arr = bytes(ptr)
    img = Image.frombytes("RGBA", (image.width(), image.height()), arr)
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def base64_to_pixmap(b64_string):
    try:
        img_data = base64.b64decode(b64_string)
        img = QImage.fromData(img_data)
        return QPixmap.fromImage(img)
    except Exception:
        return None


# @timer_function
def generate_structure_image(smiles):
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"RDKit could not parse SMILES: {smiles}")
        return None
    img = Draw.MolToImage(mol, size=(IMAGE_SIZE, IMAGE_SIZE))
    data = BytesIO()
    img.save(data, format="JPEG")
    data.seek(0)
    qt_img = QImage.fromData(data.read(), "JPEG")
    return QPixmap.fromImage(qt_img)
