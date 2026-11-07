"""Yearning-for-some-learning-v67.png for /resources/ (WordPress media; upload by hand).
Source: https://gravelgodcycling.com/wp-content/uploads/2021/01/Yearning-for-some-learning_-1-1.png saved as orig.png in D.
Run with ~/.venvs/gg-char/bin/python."""
import sys; sys.path.insert(0,'/Users/mattirowe/Documents/GravelGod/gg-art/scripts')
import render_character_art_v67 as R
import numpy as np, cv2
from PIL import Image
D='/private/tmp/claude-501/-Users-mattirowe/869009bf-e35c-4ea3-a427-b7fa6115bf0e/scratchpad/yearn/'
src=Image.open(D+'orig.png').convert('RGB'); a=np.asarray(src)[:,:,::-1].copy(); H,W=a.shape[:2]
mask=np.zeros((H,W),np.uint8); mask[:1010,520:1675]=1
mask[700:1000,1360:2010]=1
mask[1010:1150,860:1260]=1
# low-frequency fill: suppress doodles with a median, inpaint small, upscale
k=8; small=cv2.resize(cv2.medianBlur(a,21),(W//k,H//k),interpolation=cv2.INTER_AREA)
ms=cv2.dilate(cv2.resize(mask,(W//k,H//k),interpolation=cv2.INTER_NEAREST),np.ones((5,5),np.uint8))
fs=cv2.inpaint(small,ms*255,12,cv2.INPAINT_TELEA)
fs=cv2.GaussianBlur(fs,(0,0),6)
big=cv2.resize(fs,(W,H),interpolation=cv2.INTER_CUBIC).astype(np.float32)
rng=np.random.default_rng(3); noise=cv2.GaussianBlur(rng.normal(0,1,(H,W)).astype(np.float32),(0,0),1.2)*9
big+=noise[:,:,None]
soft=cv2.GaussianBlur(mask.astype(np.float32),(0,0),30)[:,:,None]; soft=np.maximum(soft,mask[:,:,None])
out=a*(1-soft)+big*soft
out[1000:H,860:1260]=a[1000:H,455:855]
out[995:1125,1360:2010]=a[995:1125,242:892][:,::-1]
img=Image.fromarray(np.clip(out,0,255).astype(np.uint8)[:,:,::-1]).convert('RGBA')
fig=R.figure('wave',face='smile',psi=67.5,crop='bust')
img=R.place(img,fig,[640,140,1400,1296],'contain','bottom')
img=R.draw_texts(img,[{"type":"bubble","text":"Yearning for some learning?","box":[1430,750,2020,1060],"tail":[1330,1010],"font":"serif","weight":700,"size":60}],1.0)
img.convert('RGB').save(D+'yearning-v67.png')
