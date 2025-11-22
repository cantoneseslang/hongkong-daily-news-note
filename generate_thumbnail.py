#!/usr/bin/env python3
"""
Gemini Proを使用して画像を生成し、一時保存するスクリプト
"""

import json
import os
import requests
import base64
from datetime import datetime
from pathlib import Path

try:
    import google.generativeai as genai
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False
    print("⚠️  google-generativeaiモジュールがインストールされていません")
    print("   インストール: pip install google-generativeai")

def generate_image_with_gemini_imagen(prompt: str, api_key: str, output_path: str) -> bool:
    """
    Gemini 2.5 Pro Image (Nano Banana Pro)を使用して画像を生成
    
    Args:
        prompt: 画像生成プロンプト
        api_key: Gemini APIキー
        output_path: 出力パス
    
    Returns:
        成功した場合True、失敗した場合False
    """
    try:
        if not HAS_GOOGLE_GENAI:
            print("❌ google-generativeaiモジュールが必要です")
            return False
        
        print("🎨 Gemini 2.5 Pro Image (Nano Banana Pro)で画像生成中...")
        
        # Gemini APIを設定
        genai.configure(api_key=api_key)
        
        # 利用可能なモデルを確認
        print("📋 利用可能なモデルを確認中...")
        try:
            models = genai.list_models()
            image_models = [m.name for m in models if 'image' in m.name.lower() or 'imagen' in m.name.lower()]
            if image_models:
                print(f"   画像生成モデル: {image_models[:5]}")
            else:
                print("   ⚠️  画像生成モデルが見つかりませんでした")
        except Exception as e:
            print(f"   ⚠️  モデルリスト取得エラー: {e}")
        
        # 画像生成専用APIを使用（Imagen 4またはGemini 2.5 Flash Image）
        # まずImagen 4を試し、失敗した場合はGemini 2.5 Flash Imageを使用
        model_id = "imagen-4.0-generate-preview-06-06"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateImages?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # プロンプトを結合
        full_prompt = f"{prompt}\n\nスタイル: リアル, 高解像度, 4K, 写真品質"
        
        payload = {
            "prompt": full_prompt,
            "numberOfImages": 1,
            "aspectRatio": "1:1"
        }
        
        print("📤 Imagen 4 API経由でリクエスト送信中...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ APIレスポンス取得成功")
            
            # 画像データを取得
            if 'generatedImages' in result and len(result['generatedImages']) > 0:
                image_data = result['generatedImages'][0].get('imageBytes')
                
                if image_data:
                    # base64デコードして保存
                    image_bytes = base64.b64decode(image_data)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    print(f"✅ 画像を保存しました: {output_path}")
                    return True
                elif 'imageUrl' in result['generatedImages'][0]:
                    # URLから画像をダウンロード
                    image_url = result['generatedImages'][0]['imageUrl']
                    print(f"📥 画像をダウンロード中: {image_url}")
                    img_response = requests.get(image_url, timeout=30)
                    
                    if img_response.status_code == 200:
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(img_response.content)
                        print(f"✅ 画像を保存しました: {output_path}")
                        return True
                    else:
                        print(f"❌ 画像ダウンロードエラー: HTTP {img_response.status_code}")
                        return False
                else:
                    print(f"❌ 画像データが見つかりませんでした")
                    print(f"   レスポンス: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                    return False
            else:
                print(f"❌ 生成された画像が見つかりませんでした")
                print(f"   レスポンス: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                return False
        else:
            print(f"❌ Imagen APIエラー: HTTP {response.status_code}")
            print(f"   レスポンス: {response.text[:500]}")
            # Gemini 2.5 Flash Imageにフォールバック
            print("🔄 Imagen 4失敗、Gemini 2.5 Flash Imageにフォールバック...")
            return _generate_image_with_gemini_flash_image(prompt, api_key, output_path)
            
    except Exception as e:
        print(f"❌ Gemini画像生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def _generate_image_with_gemini_flash_image(prompt: str, api_key: str, output_path: str) -> bool:
    """
    Gemini 2.5 Flash Imageを使用して画像を生成（フォールバック用）
    """
    try:
        print("🎨 Gemini 2.5 Flash Imageで画像生成中...")
        
        model_id = "gemini-2.5-flash-image"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        full_prompt = f"{prompt}\n\nスタイル: リアル, 高解像度, 4K, 写真品質"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }]
        }
        
        print("📤 REST API経由でリクエスト送信中...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            
            # 画像データを取得
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    for part in candidate['content']['parts']:
                        if 'inlineData' in part:
                            image_data = part['inlineData']['data']
                            image_bytes = base64.b64decode(image_data)
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            with open(output_path, 'wb') as f:
                                f.write(image_bytes)
                            print(f"✅ 画像を保存しました: {output_path}")
                            return True
            
            print(f"❌ 画像データが見つかりませんでした")
            return False
        else:
            print(f"❌ Gemini Flash Image APIエラー: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Gemini Flash Image画像生成エラー: {e}")
        return False
        
        # 画像の保存
        if response.parts:
            image = response.parts[0].image
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            image.save(output_path)
            print(f"✅ 画像を保存しました: {output_path}")
            return True
        else:
            print("❌ 画像が生成されませんでした")
            if hasattr(response, 'prompt_feedback'):
                print(f"   フィードバック: {response.prompt_feedback}")
            return False
            
    except Exception as e:
        print(f"❌ Gemini画像生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_image_with_replicate(prompt: str, replicate_api_key: str, output_path: str) -> bool:
    """
    Replicate APIを使用してStable Diffusionで画像を生成
    
    Args:
        prompt: 画像生成プロンプト
        replicate_api_key: Replicate APIキー
        output_path: 出力パス
    
    Returns:
        成功した場合True、失敗した場合False
    """
    try:
        print("🎨 Replicate API (Stable Diffusion)で画像生成中...")
        
        import replicate
        
        # Replicateクライアントを初期化
        client = replicate.Client(api_token=replicate_api_key)
        
        # Stable Diffusion XLモデルを使用
        output = client.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={"prompt": prompt}
        )
        
        # 出力はURLのリスト
        if output and len(output) > 0:
            image_url = output[0] if isinstance(output, list) else output
            
            # 画像をダウンロード
            print(f"📥 画像をダウンロード中: {image_url}")
            img_response = requests.get(image_url, timeout=30)
            
            if img_response.status_code == 200:
                # 画像を保存
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(img_response.content)
                
                print(f"✅ 画像を保存しました: {output_path}")
                return True
            else:
                print(f"❌ 画像ダウンロードエラー: HTTP {img_response.status_code}")
                return False
        else:
            print("❌ 画像生成失敗: 出力が空です")
            return False
            
    except ImportError:
        print("⚠️  replicateモジュールがインストールされていません")
        print("   インストール: pip install replicate")
        return False
    except Exception as e:
        print(f"❌ Replicate画像生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_image_with_stable_diffusion(prompt: str, output_path: str) -> bool:
    """
    Hugging Face Stable Diffusion APIを使用して画像を生成
    
    Args:
        prompt: 画像生成プロンプト
        output_path: 出力パス
    
    Returns:
        成功した場合True、失敗した場合False
    """
    try:
        print("🎨 Hugging Face Stable Diffusion APIで画像生成中...")
        
        # 新しいHugging Face Router APIを使用
        url = "https://router.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 50,
                "guidance_scale": 7.5
            }
        }
        
        print("📤 リクエスト送信中...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            # 画像データを保存
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ 画像を保存しました: {output_path}")
            return True
        elif response.status_code == 503:
            # モデルがロード中の場合は少し待って再試行
            print("⏳ モデルがロード中です。30秒待機して再試行します...")
            import time
            time.sleep(30)
            return generate_image_with_stable_diffusion(prompt, output_path)
        else:
            print(f"❌ Stable Diffusion APIエラー: HTTP {response.status_code}")
            print(f"   レスポンス: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Stable Diffusion画像生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_image_with_dalle(prompt: str, openai_api_key: str, output_path: str) -> bool:
    """
    OpenAI DALL-E APIを使用して画像を生成
    
    Args:
        prompt: 画像生成プロンプト
        openai_api_key: OpenAI APIキー
        output_path: 出力パス
    
    Returns:
        成功した場合True、失敗した場合False
    """
    try:
        print("🎨 DALL-E APIで画像生成中...")
        
        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "quality": "hd"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            image_url = result['data'][0]['url']
            
            # 画像をダウンロード
            print(f"📥 画像をダウンロード中: {image_url}")
            img_response = requests.get(image_url, timeout=30)
            
            if img_response.status_code == 200:
                # 画像を保存
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(img_response.content)
                
                print(f"✅ 画像を保存しました: {output_path}")
                return True
            else:
                print(f"❌ 画像ダウンロードエラー: HTTP {img_response.status_code}")
                return False
        else:
            print(f"❌ DALL-E APIエラー: HTTP {response.status_code}")
            print(f"   レスポンス: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ DALL-E画像生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_thumbnail_for_article(prompt: str, config_path: str = "config.json", output_dir: str = "images") -> str:
    """
    記事用の見出し画像を生成
    
    Args:
        prompt: 画像生成プロンプト
        config_path: 設定ファイルのパス
        output_dir: 出力ディレクトリ
    
    Returns:
        生成された画像のパス（失敗した場合は空文字列）
    """
    # 設定ファイルを読み込み
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # APIキーを取得（優先順位: Replicate > OpenAI > Hugging Face）
    replicate_api_key = None
    openai_api_key = None
    gemini_api_key = None
    
    if 'replicate_api' in config and config['replicate_api'].get('api_key'):
        replicate_api_key = config['replicate_api']['api_key']
    
    if 'openai_api' in config and config['openai_api'].get('api_key'):
        openai_api_key = config['openai_api']['api_key']
    
    if 'gemini_api' in config and config['gemini_api'].get('api_key'):
        gemini_api_key = config['gemini_api']['api_key']
    
    # 出力パスを生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"article-header-{timestamp}.png")
    
    # 画像生成（優先順位: Imagen > Replicate > Hugging Face > DALL-E）
    success = False
    
    if gemini_api_key:
        print("🎨 Google Imagen APIを試行中...")
        success = generate_image_with_gemini_imagen(prompt, gemini_api_key, output_path)
    
    if not success and replicate_api_key:
        print("🔄 Imagen API失敗、Replicate APIにフォールバック...")
        success = generate_image_with_replicate(prompt, replicate_api_key, output_path)
    
    if not success:
        print("🔄 Replicate API失敗、Hugging Face APIにフォールバック...")
        success = generate_image_with_stable_diffusion(prompt, output_path)
    
    if not success and openai_api_key:
        print("🔄 Hugging Face API失敗、DALL-E APIにフォールバック...")
        success = generate_image_with_dalle(prompt, openai_api_key, output_path)
    
    if not success:
        print("❌ エラー: すべての画像生成APIが失敗しました")
        return ""
    
    if success:
        return output_path
    else:
        return ""

if __name__ == "__main__":
    # テスト用のプロンプト
    test_prompt = """Ultra-realistic outdoor news reporting scene, 4K resolution.

Location: A real street in Hong Kong during daytime.

Tall buildings and dense urban scenery around, with signage, traffic, people in the background naturally blurred with shallow depth of field.

Humidity and soft daylight typical of Hong Kong.

Foreground: Two young Japanese news anchors standing side by side outdoors, real human appearance,smiling lightly and facing the camera.

Both anchors hold handheld reporter microphones with foam windscreens.

4. Foreground: Two young Japanese news anchors standing side by side with smile expressions, facing the camera, enlarged to dominate the foreground; 

the man on the left has short black hair, 

wearing a milky brown suit, light blue shirt, and light orange tie; the woman on the right has shoulder-length brown hair with pony tail wearing the glasses, wearing a light yellow  blouse and sky blue skirt.

Behind the anchors:

A Hong Kong-style old neon signboard displaying the Japanese text "香 港 新 聞" mounted on a building exterior.

Features:

slightly weathered, retro Hong Kong neon sign.glowing red & pink neon tubes with uneven flicker.metal frame with rust, aged acrylic.moody neon bloom but still realistic and photographic

Cameraman & crew visible:

A professional camera crew is clearly visible in the shot:

A camera operator using a shoulder-mounted broadcast camera filming the anchors

A boom mic operator partially visible

Cables, light reflectors, or small equipment cases around them

Everything must look 100% real and documentary-style, not staged studio lighting.

Ticker bar overlay:

At the bottom of the image, a news-style headline ticker in white Japanese text:

"中日摩擦：日本ツアーの問い合わせが2～3割減、旅行会社役員が発言"

Small bottom-right text:

"HK NEWS 2025 11 21" in clean black English font.

Style:

Realistic outdoor news reportage.

Handheld-camera feeling, shallow depth of field, natural lighting.

Contrast between the cool urban daylight and the warm red/pink neon sign.

Shot with a full-frame DSLR, 35mm or 50mm lens.

No anime, no illustration, no cartoon, no CGI — pure real-life photography."""
    
    print("=" * 60)
    print("🎨 見出し画像生成テスト")
    print("=" * 60)
    
    result_path = generate_thumbnail_for_article(test_prompt)
    
    if result_path:
        print(f"\n✅ 画像生成成功: {result_path}")
    else:
        print("\n❌ 画像生成失敗")

