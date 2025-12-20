"""
VibeVoice 한글 TTS 웹 인터페이스
Gradio를 사용한 간단한 웹 UI

실행: python web_tts.py
접속: http://localhost:7860
"""
import gradio as gr
import os
import sys
import time
import copy
import traceback as tb

def generate_speech(text, speaker_name, cfg_scale):
    """텍스트를 음성으로 변환"""
    if not text or not text.strip():
        return None, "❌ 텍스트를 입력해주세요."
    
    try:
        import torch
        from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
        from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
        
        # 텍스트 전처리
        text = text.strip().replace("'", "'").replace('"', '"').replace('"', '"')
        
        # 디바이스 설정
        if torch.cuda.is_available():
            device = 'cuda'
        elif torch.backends.mps.is_available():
            device = 'mps'
        else:
            device = 'cpu'
        
        status_msg = f"🖥️ 디바이스: {device}\n"
        
        # 모델 로드 (전역 변수로 캐싱하면 더 빠름)
        model_path = 'microsoft/VibeVoice-Realtime-0.5B'
        
        status_msg += f"📦 모델 로딩 중...\n"
        processor = VibeVoiceStreamingProcessor.from_pretrained(model_path)
        
        # 디바이스별 설정
        if device == 'mps':
            load_dtype = torch.float32
            attn_impl = 'sdpa'
        elif device == 'cuda':
            load_dtype = torch.bfloat16
            attn_impl = 'flash_attention_2'
        else:
            load_dtype = torch.float32
            attn_impl = 'sdpa'
        
        try:
            if device == 'mps':
                model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                    model_path, torch_dtype=load_dtype, attn_implementation=attn_impl, device_map=None
                )
                model.to('mps')
            elif device == 'cuda':
                model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                    model_path, torch_dtype=load_dtype, device_map='cuda', attn_implementation=attn_impl
                )
            else:
                model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                    model_path, torch_dtype=load_dtype, device_map='cpu', attn_implementation=attn_impl
                )
        except:
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path, torch_dtype=load_dtype, 
                device_map=(device if device in ('cuda', 'cpu') else None), 
                attn_implementation='sdpa'
            )
            if device == 'mps':
                model.to('mps')
        
        model.eval()
        model.set_ddpm_inference_steps(num_steps=5)
        
        # 화자 음성 파일 찾기
        possible_voice_dirs = [
            os.path.join('VibeVoice', 'demo', 'voices', 'streaming_model'),
            os.path.join(os.path.expanduser('~'), 'VibeVoice', 'demo', 'voices', 'streaming_model'),
        ]
        
        voice_file = None
        for voice_dir in possible_voice_dirs:
            if os.path.exists(voice_dir):
                for filename in os.listdir(voice_dir):
                    if filename.endswith('.pt') and speaker_name.lower() in filename.lower():
                        voice_file = os.path.join(voice_dir, filename)
                        break
                if voice_file:
                    break
        
        if not voice_file or not os.path.exists(voice_file):
            return None, f"❌ '{speaker_name}' 화자 파일을 찾을 수 없습니다.\nVibeVoice/demo/voices/streaming_model/ 폴더를 확인하세요."
        
        status_msg += f"🎤 화자: {speaker_name}\n"
        
        target_device = device if device != 'cpu' else 'cpu'
        all_prefilled_outputs = torch.load(voice_file, map_location=target_device, weights_only=False)
        
        # 입력 준비
        inputs = processor.process_input_with_cached_prompt(
            text=text, cached_prompt=all_prefilled_outputs,
            padding=True, return_tensors='pt', return_attention_mask=True
        )
        
        for k, v in inputs.items():
            if torch.is_tensor(v):
                inputs[k] = v.to(target_device)
        
        # 음성 생성
        status_msg += f"🎵 음성 생성 중...\n"
        start_time = time.time()
        
        outputs = model.generate(
            **inputs, max_new_tokens=None, cfg_scale=cfg_scale,
            tokenizer=processor.tokenizer, generation_config={'do_sample': False},
            verbose=False,
            all_prefilled_outputs=copy.deepcopy(all_prefilled_outputs) if all_prefilled_outputs is not None else None
        )
        
        generation_time = time.time() - start_time
        
        # 통계
        if outputs.speech_outputs and outputs.speech_outputs[0] is not None:
            sample_rate = 24000
            audio_samples = outputs.speech_outputs[0].shape[-1]
            audio_duration = audio_samples / sample_rate
            rtf = generation_time / audio_duration
            
            status_msg += f"⏱️ 생성 시간: {generation_time:.2f}초\n"
            status_msg += f"🎶 오디오 길이: {audio_duration:.2f}초\n"
            status_msg += f"⚡ RTF: {rtf:.2f}x\n"
            status_msg += "✅ 완료!"
            
            # 임시 파일로 저장
            output_path = "temp_output.wav"
            processor.save_audio(outputs.speech_outputs[0], output_path=output_path)
            
            return output_path, status_msg
        else:
            return None, "❌ 음성 생성 실패"
            
    except ImportError as e:
        error_msg = f"❌ 라이브러리 import 실패: {e}\n\n"
        error_msg += "📌 해결 방법:\n"
        error_msg += "1. pip install -r requirements.txt\n"
        error_msg += "2. git clone https://github.com/microsoft/VibeVoice.git\n"
        error_msg += "3. cd VibeVoice && pip install -e ."
        return None, error_msg
    except Exception as e:
        error_msg = f"❌ 에러 발생: {e}\n\n"
        error_msg += tb.format_exc()
        return None, error_msg

# Gradio 인터페이스
with gr.Blocks(title="VibeVoice 한글 TTS") as demo:
    gr.Markdown("""
    # 🎙️ VibeVoice 한글 TTS 서비스
    
    Microsoft의 VibeVoice-Realtime-0.5B 모델을 사용한 Text-to-Speech 웹 인터페이스입니다.
    
    > ⚠️ **주의**: 이 서비스는 공식적으로 영어 전용이지만, 실험적으로 한글도 지원합니다.
    """)
    
    with gr.Row():
        with gr.Column():
            text_input = gr.Textbox(
                label="변환할 텍스트",
                placeholder="여기에 한글 텍스트를 입력하세요...",
                lines=5
            )
            
            speaker_dropdown = gr.Dropdown(
                choices=["Carter", "Wayne", "Emma", "Lily"],
                value="Carter",
                label="화자 선택"
            )
            
            cfg_slider = gr.Slider(
                minimum=1.0,
                maximum=3.0,
                value=1.5,
                step=0.1,
                label="CFG Scale (음성 품질 조절)"
            )
            
            generate_btn = gr.Button("🎵 음성 생성", variant="primary")
        
        with gr.Column():
            audio_output = gr.Audio(label="생성된 음성", type="filepath")
            status_output = gr.Textbox(label="상태", lines=10)
    
    # 예시 텍스트
    gr.Examples(
        examples=[
            ["안녕하세요. VibeVoice 한글 TTS 테스트입니다.", "Carter", 1.5],
            ["오늘 날씨가 참 좋네요. 여러분의 하루가 행복하기를 바랍니다.", "Wayne", 1.5],
            ["인공지능 음성 합성 기술이 점점 발전하고 있습니다.", "Carter", 1.5],
        ],
        inputs=[text_input, speaker_dropdown, cfg_slider],
    )
    
    # 이벤트 연결
    generate_btn.click(
        fn=generate_speech,
        inputs=[text_input, speaker_dropdown, cfg_slider],
        outputs=[audio_output, status_output]
    )

if __name__ == "__main__":
    print("🚀 VibeVoice 웹 인터페이스를 시작합니다...")
    print("📌 브라우저에서 http://localhost:7860 으로 접속하세요.")
    print()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
