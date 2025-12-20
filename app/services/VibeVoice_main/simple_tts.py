"""
VibeVoice 한글 TTS 간단 CLI 실행 스크립트
사용법: python simple_tts.py --txt_path <텍스트파일경로> --output <저장경로>
"""
import os
import argparse
import time
import torch
import copy
from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor

def main():
    parser = argparse.ArgumentParser(description="VibeVoice 한글 TTS CLI")
    parser.add_argument("--txt_path", type=str, required=True, help="입력 텍스트 파일 경로")
    parser.add_argument("--output", type=str, default="output.wav", help="저장할 오디오 파일 경로")
    parser.add_argument("--speaker_name", type=str, default="Carter", help="화자 이름 (VibeVoice/demo/voices/streaming_model/ 내 파일 매칭)")
    parser.add_argument("--cfg_scale", type=float, default=1.5, help="CFG Scale (1.0 ~ 3.0)")
    args = parser.parse_args()

    # 1. 텍스트 읽기
    if not os.path.exists(args.txt_path):
        print(f"❌ 파일이 없습니다: {args.txt_path}")
        return

    with open(args.txt_path, 'r', encoding='utf-8') as f:
        text = f.read().strip()
    
    if not text:
        print("❌ 텍스트 파일이 비어 있습니다.")
        return

    print(f"📝 입력 텍스트: {text[:50]}..." if len(text) > 50 else f"📝 입력 텍스트: {text}")

    # 2. 모델 로드
    print("📦 모델 로딩 중...")
    model_path = 'microsoft/VibeVoice-Realtime-0.5B'
    
    # Device 설정
    if torch.cuda.is_available():
        device = 'cuda'
        load_dtype = torch.bfloat16
        attn_impl = 'flash_attention_2'
    elif torch.backends.mps.is_available():
        device = 'mps'
        load_dtype = torch.float32
        attn_impl = 'sdpa'
    else:
        device = 'cpu'
        load_dtype = torch.float32
        attn_impl = 'sdpa'

    print(f"🖥️  디바이스: {device}")

    processor = VibeVoiceStreamingProcessor.from_pretrained(model_path)
    
    try:
        if device == 'cuda':
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path, torch_dtype=load_dtype, device_map='cuda', attn_implementation=attn_impl
            )
        elif device == 'mps':
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path, torch_dtype=load_dtype, attn_implementation=attn_impl, device_map=None
            )
            model.to('mps')
        else:
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path, torch_dtype=load_dtype, device_map='cpu', attn_implementation=attn_impl
            )
    except:
        # Fallback
        model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
            model_path, torch_dtype=load_dtype, 
            device_map=(device if device in ('cuda', 'cpu') else None), 
            attn_implementation='sdpa'
        )
        if device == 'mps':
            model.to('mps')

    model.eval()
    model.set_ddpm_inference_steps(num_steps=5)

    # 3. 화자 파일 찾기
    possible_voice_dirs = [
        os.path.join('VibeVoice', 'demo', 'voices', 'streaming_model'),
        os.path.join(os.path.expanduser('~'), 'VibeVoice', 'demo', 'voices', 'streaming_model'),
    ]
    
    voice_file = None
    for voice_dir in possible_voice_dirs:
        if os.path.exists(voice_dir):
            for filename in os.listdir(voice_dir):
                if filename.endswith('.pt') and args.speaker_name.lower() in filename.lower():
                    voice_file = os.path.join(voice_dir, filename)
                    break
            if voice_file:
                break
    
    if not voice_file:
        print(f"❌ '{args.speaker_name}' 화자 파일을 찾을 수 없습니다.")
        return

    print(f"🎤 화자: {args.speaker_name}")
    
    target_device = device if device != 'cpu' else 'cpu'
    all_prefilled_outputs = torch.load(voice_file, map_location=target_device, weights_only=False)

    # 4. 입력 처리
    text = text.replace("'", "'").replace('"', '"').replace('"', '"')
    inputs = processor.process_input_with_cached_prompt(
        text=text, cached_prompt=all_prefilled_outputs,
        padding=True, return_tensors='pt', return_attention_mask=True
    )

    for k, v in inputs.items():
        if torch.is_tensor(v):
            inputs[k] = v.to(target_device)

    # 5. 생성
    print("🎵 음성 생성 중...")
    start_time = time.time()
    
    outputs = model.generate(
        **inputs, max_new_tokens=None, cfg_scale=args.cfg_scale,
        tokenizer=processor.tokenizer, generation_config={'do_sample': False},
        verbose=False,
        all_prefilled_outputs=copy.deepcopy(all_prefilled_outputs)
    )
    
    generation_time = time.time() - start_time
    
    # 6. 저장
    if outputs.speech_outputs and outputs.speech_outputs[0] is not None:
        processor.save_audio(outputs.speech_outputs[0], output_path=args.output)
        print(f"✅ 저장 완료: {args.output}")
        print(f"⏱️  소요 시간: {generation_time:.2f}초")
    else:
        print("❌ 생성 실패")

if __name__ == "__main__":
    main()
