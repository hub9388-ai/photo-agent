"""Local brush API add/lasso/subtract checks. No model call."""
import io
import json
import secrets
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(CookieJar()))
    def request(path, payload=None, raw=None, content_type="application/json", method=None):
        data = json.dumps(payload).encode() if payload is not None else raw
        req = urllib.request.Request("http://127.0.0.1:7301" + path, data=data, method=method,
                                     headers={"Content-Type": content_type})
        with opener.open(req, timeout=30) as response:
            data = response.read()
            return json.loads(data) if data else None
    def alpha(selection):
        with opener.open(selection["mask"]["url"], timeout=30) as response:
            return Image.open(io.BytesIO(response.read())).convert("RGBA").getchannel("A")

    request("/api/auth/register", {"username":"brush_accept_"+secrets.token_hex(5), "password":secrets.token_urlsafe(24)})
    stream = io.BytesIO()
    Image.new("RGB", (100,100), (80,100,120)).save(stream,"PNG")
    boundary = "brush" + secrets.token_hex(8)
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="brush.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + stream.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    asset = request("/api/assets", raw=body, content_type=f"multipart/form-data; boundary={boundary}")
    original = request("/api/sessions", {"current_asset_id":asset["id"],"title":"Brush isolated acceptance"})
    prefix = f"/api/sessions/{original['id']}"
    stroke = [{"x":.2,"y":.2},{"x":.8,"y":.2},{"x":.8,"y":.8}]
    payload = {"revision":original["revision"],"radius":.04,"strokes":[stroke],"shape":"paint","operation":"add"}
    paint = alpha(request(prefix+"/selection",payload))
    assert paint.getpixel((65,35)) == 0 and paint.getpixel((50,20)) == 255
    lasso = alpha(request(prefix+"/selection",{**payload,"shape":"lasso"}))
    assert lasso.getpixel((65,35)) == 255
    erased = alpha(request(prefix+"/selection",{**payload,"operation":"subtract","radius":.08,
                                               "strokes":[[{"x":.65,"y":.2},{"x":.65,"y":.6}]]}))
    assert erased.getpixel((65,35)) == 0 and erased.getpixel((20,20)) == 255
    request(prefix+"/selection", method="DELETE")
    assert request(prefix+"/selection") is None
    current = request(prefix)
    assert current["revision"] == original["revision"] and current["current_asset_id"] == asset["id"]
    report={"status":"passed","session_id":original["id"],"paint_not_filled":True,"lasso_filled":True,
            "subtract_removed_only_selected_stroke":True,"clear_succeeded":True,"original_and_revision_unchanged":True,
            "model_requests":0,"scope":"local synthetic image API/mask semantics, not browser or portrait quality"}
    out=ROOT/".test_artifacts"/"portrait-brush"
    out.mkdir(exist_ok=True)
    (out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
