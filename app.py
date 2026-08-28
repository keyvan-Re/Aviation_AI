import sys
import os
import json
import base64
from openai import OpenAI
import streamlit as st
import streamlit.components.v1 as components  # اضافه شده برای دکمه کپی
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from typing import List
import auth

print(">>> LOG: app.py execution started. Initializing...")

auth.init_db()

def get_image_base64(uploaded_file):
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode('utf-8')

# --- [تابع جدید برای رندر کردن دکمه کپی زیر هر پیام] ---
def render_copy_button(text):
    # تبدیل متن به Base64 برای جلوگیری از تداخل کاراکترهای خاص در جاوا اسکریپت
    b64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    
    html_code = f"""
    <script>
    function copyText() {{
        const text = decodeURIComponent(escape(window.atob('{b64_text}')));
        
        function showSuccess() {{
            const btn = document.getElementById('copy-btn');
            btn.innerHTML = '✅ Copied!';
            setTimeout(() => btn.innerHTML = '📋 Copy', 2000);
        }}

        if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(text).then(showSuccess).catch(err => console.error(err));
        }} else {{
            let textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                document.execCommand('copy');
                showSuccess();
            }} catch (err) {{
                console.error('Fallback copy failed', err);
            }}
            textArea.remove();
        }}
    }}
    </script>
    <style>
    body {{ margin: 0; padding: 0; background-color: transparent; }}
    #copy-btn {{
        background-color: transparent;
        border: 1px solid rgba(128, 128, 128, 0.4);
        color: #888;
        padding: 4px 10px;
        text-align: center;
        display: inline-block;
        font-size: 13px;
        border-radius: 5px;
        cursor: pointer;
        transition-duration: 0.2s;
        font-family: sans-serif;
        margin-bottom: 5px;
    }}
    #copy-btn:hover {{
        border-color: #888;
        color: #fff;
        background-color: rgba(128, 128, 128, 0.1);
    }}
    @media (prefers-color-scheme: light) {{
        #copy-btn {{ color: #555; }}
        #copy-btn:hover {{ color: #000; background-color: rgba(0, 0, 0, 0.05); }}
    }}
    </style>
    <button id="copy-btn" onclick="copyText()">📋 Copy</button>
    """
    components.html(html_code, height=35)
# ---------------------------------------------------------

# --- [مدیریت Session State ها] ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ''
if 'current_chat_id' not in st.session_state:
    st.session_state.current_chat_id = None
if 'file_uploader_key' not in st.session_state:
    st.session_state.file_uploader_key = 0
if 'editing_last' not in st.session_state:
    st.session_state.editing_last = False
if 'edit_text' not in st.session_state:
    st.session_state.edit_text = ""
if 'pending_prompt' not in st.session_state:
    st.session_state.pending_prompt = None
# متغیر جدید برای حفظ موقت منابعِ آخرین پیام هنگام Refresh شدن صفحه
if 'latest_sources' not in st.session_state:
    st.session_state.latest_sources = {}

if not st.session_state.logged_in:
    auth.show_login_page()
else:
    st.sidebar.write(f"👤 User: **{st.session_state.username}**")
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ''
        st.session_state.current_chat_id = None
        st.rerun()

    st.sidebar.divider()
    
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_id = auth.create_new_chat(st.session_state.username)
        st.session_state.current_chat_id = new_id
        st.rerun()

    st.sidebar.write("**Active Chats:**")
    active_chats = auth.get_user_chats(st.session_state.username)
    archived_chats = auth.get_archived_chats(st.session_state.username)
    
    all_valid_chat_ids = [c[0] for c in active_chats] + [c[0] for c in archived_chats]
    if st.session_state.current_chat_id not in all_valid_chat_ids:
        if active_chats:
            st.session_state.current_chat_id = active_chats[0][0]
        else:
            default_chat_id = auth.create_new_chat(st.session_state.username)
            st.session_state.current_chat_id = default_chat_id
            active_chats = auth.get_user_chats(st.session_state.username)

    for chat_id, title in active_chats:
        col1, col2 = st.sidebar.columns([8, 2])
        is_active = (chat_id == st.session_state.current_chat_id)
        btn_label = f"💬 {title}" if is_active else title
        
        with col1:
            if st.button(btn_label, key=f"chat_btn_{chat_id}", use_container_width=True):
                st.session_state.current_chat_id = chat_id
                st.rerun()
                
        with col2:
            with st.popover("⋮", use_container_width=True):
                new_title = st.text_input("Rename", value=title, key=f"ren_{chat_id}")
                if st.button("Save", key=f"save_{chat_id}"):
                    auth.update_chat_title(chat_id, new_title)
                    st.rerun()
                
                if st.button("Archive 📁", key=f"arc_{chat_id}"):
                    auth.archive_chat(chat_id)
                    st.rerun()
                
                st.divider()
                st.markdown("**Delete Chat**")
                confirm_delete = st.checkbox("Are you sure?", key=f"chk_del_{chat_id}")
                if confirm_delete:
                    if st.button("Confirm Delete 🗑️", key=f"del_{chat_id}"):
                        auth.delete_chat(chat_id)
                        st.rerun()

    if archived_chats:
        with st.sidebar.expander("📁 Archived Chats"):
            for chat_id, title in archived_chats:
                col1, col2 = st.columns([8, 2])
                is_active = (chat_id == st.session_state.current_chat_id)
                btn_label = f"📄 {title}" if is_active else title
                
                with col1:
                    if st.button(btn_label, key=f"arch_btn_{chat_id}", use_container_width=True):
                        st.session_state.current_chat_id = chat_id
                        st.rerun()
                with col2:
                    with st.popover("⋮", key=f"arch_pop_{chat_id}"):
                        st.markdown("**Delete Chat**")
                        confirm_delete = st.checkbox("Are you sure?", key=f"chk_del_arch_{chat_id}")
                        if confirm_delete:
                            if st.button("Confirm Delete 🗑️", key=f"del_arch_{chat_id}"):
                                auth.delete_chat(chat_id)
                                st.rerun()
    
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    BASE_URL = os.environ.get("BASE_URL")
    
    if not OPENAI_API_KEY or not BASE_URL:
        st.error("FATAL ERROR: `OPENAI_API_KEY` or `BASE_URL` not found in environment variables.")
        st.stop()

    st.title("✈️ Aviation AI Assistant")

    @st.cache_resource
    def load_vector_db():
        embeddings = OpenAIEmbeddings(
            openai_api_key=OPENAI_API_KEY, 
            openai_api_base=BASE_URL,
            request_timeout=30
        )
        db = FAISS.load_local("my_vector_db", embeddings, allow_dangerous_deserialization=True)
        return db.as_retriever(search_kwargs={"k": 3})

    try:
        retriever = load_vector_db()
    except Exception as e:
        st.error(f"Error loading vector database: {e}")
        st.stop()

    llm = ChatOpenAI(
        model_name="gpt-4o", 
        openai_api_key=OPENAI_API_KEY, 
        base_url=BASE_URL,
        request_timeout=45
    )
    openai_client = OpenAI(
        api_key=OPENAI_API_KEY, 
        base_url=BASE_URL,
        timeout=30
    )
    
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer")
    
    db_messages = auth.get_chat_messages(st.session_state.current_chat_id)
    
    for i in range(0, len(db_messages) - 1, 2):
        if db_messages[i]["role"] == "user" and i+1 < len(db_messages):
            memory.save_context({"question": db_messages[i]["content"]}, 
                                {"answer": db_messages[i+1]["content"]})

    # --- [نمایش تاریخچه چت] ---
    for i, msg in enumerate(db_messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # ---> فراخوانی دکمه کپی برای هر پیام (سوال و جواب) <---
            render_copy_button(msg["content"])
            
            # 1. اگر در دیتابیس منابعی داشتیم (فعلا دیتابیس فقط متن ذخیره میکند)
            if msg["role"] == "assistant" and len(msg.get("sources", [])) > 0:
                with st.expander("📑 Sources Used"):
                    for j, doc_dict in enumerate(msg["sources"]):
                        page_number = doc_dict.get('page', 0) + 1
                        source_name = doc_dict.get('source', f'Source {j+1}')
                        st.write(f"**Source: {source_name} (Page {page_number}):**")
                        st.write(doc_dict.get('content', ''))
                        
            # 2. نمایش منابع موقت (برای آخرین پیام پردازش شده تا در صورت رفرش از بین نرود)
            elif msg["role"] == "assistant" and i == len(db_messages) - 1:
                chat_id = st.session_state.current_chat_id
                if chat_id in st.session_state.latest_sources and st.session_state.latest_sources[chat_id]:
                    with st.expander("📑 Sources Used"):
                        for j, doc_dict in enumerate(st.session_state.latest_sources[chat_id]):
                            page_number = doc_dict.get('page', 0) + 1
                            source_name = doc_dict.get('source', f'Source {j+1}')
                            st.write(f"**Source: {source_name} (Page {page_number}):**")
                            st.write(doc_dict.get('content', ''))

    is_current_archived = any(c[0] == st.session_state.current_chat_id for c in archived_chats)
    
    if is_current_archived:
        st.warning("این چت آرشیو شده است و فقط قابل خواندن میباشد.")
    else:
        last_user_msg = None
        for msg in reversed(db_messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg and not st.session_state.editing_last:
            col_spacer, col_btn = st.columns([8, 2])
            with col_btn:
                if st.button("✏️ Edit", use_container_width=True):
                    st.session_state.editing_last = True
                    st.session_state.edit_text = last_user_msg
                    st.rerun()

        if st.session_state.editing_last:
            with st.container():
                st.info("Edit last question (upon confirmation, the previous conversation will be deleted and replaced):")
                new_text = st.text_area("Question", value=st.session_state.edit_text, label_visibility="collapsed")
                c1, c2, c3 = st.columns([2, 2, 6])
                with c1:
                    if st.button("✔️ Submit Edit", use_container_width=True):
                        auth.delete_last_interaction(st.session_state.current_chat_id)
                        st.session_state.editing_last = False
                        st.session_state.pending_prompt = new_text
                        st.rerun()
                with c2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.editing_last = False
                        st.rerun()

        col1, col2, _ = st.columns([2, 2, 6])
        with col1:
            with st.popover("Attach", icon=":material/attachment:", help="Upload Image or Map"):
                uploaded_image = st.file_uploader(
                    "Select File", 
                    type=["png", "jpg", "jpeg"], 
                    key=f"img_uploader_{st.session_state.current_chat_id}_{st.session_state.file_uploader_key}"
                )
        with col2:
            with st.popover("Voice", icon=":material/mic:", help="Record a voice message"):
                recorded_audio = st.audio_input(
                    "Record your message",
                    key=f"audio_uploader_{st.session_state.current_chat_id}_{st.session_state.file_uploader_key}"
                )
            
        if uploaded_image:
            st.info(f"✅ Image '{uploaded_image.name}' attached.")
        if recorded_audio:
            st.info("✅ Voice message recorded. Submit to transcribe and ask.")

        text_prompt = st.chat_input("Ask your question...")
        final_prompt = None
        
        if st.session_state.pending_prompt:
            final_prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None
            
        elif text_prompt:
            final_prompt = text_prompt
            
        elif recorded_audio:
            with st.spinner("🗣️ Transcribing voice..."):
                try:
                    recorded_audio.name = "audio.wav" 
                    transcript = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=recorded_audio
                    )
                    final_prompt = transcript.text
                except Exception as e:
                    st.error(f"خطا در تبدیل صدا به متن. لطفاً دوباره تلاش کنید: {e}")
                    st.stop()

        if final_prompt:
            if len(db_messages) == 0:
                auth.update_chat_title(st.session_state.current_chat_id, final_prompt[:30] + "...")
            
            with st.chat_message("user"): 
                st.markdown(final_prompt)
                if uploaded_image:
                    st.image(uploaded_image, width=300)
                    
            auth.save_message(st.session_state.current_chat_id, "user", final_prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("Thinking & Analyzing..."):
                    
                    image_context = ""
                    base64_image = None
                    if uploaded_image:
                        base64_image = get_image_base64(uploaded_image)
                        try:
                            vision_prompt = "Briefly describe this aviation-related image, part, or schematic in 1-2 sentences. Focus on identifying parts, defects, or key features."
                            caption_msg = HumanMessage(content=[
                                {"type": "text", "text": vision_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ])
                            caption_result = llm.invoke([caption_msg])
                            image_context = caption_result.content
                            st.caption(f"*(👁️ Image Analysis: {image_context})*")
                        except Exception as e:
                            print(f"Vision pre-processing failed: {e}")

                    trivial_phrases = ["hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "good morning", "good afternoon"]
                    is_trivial = final_prompt.strip().lower() in trivial_phrases
                    
                    source_docs = []
                    context_text = ""
                    
                    if is_trivial and not uploaded_image:
                        system_prompt = "You are an expert Aviation AI Assistant. The user just greeted you or said thanks. Reply politely and briefly, asking how you can help them with aviation or aircraft maintenance today."
                    
                    else:
                        combined_user_input = final_prompt
                        if image_context:
                            combined_user_input = f"User asks: '{final_prompt}' about an image showing: {image_context}"

                        search_query = combined_user_input
                        chat_history_msgs = memory.chat_memory.messages
                        
                        if len(chat_history_msgs) > 0:
                            chat_history_str = "\n".join([
                                f"{'User' if msg.type == 'human' else 'Assistant'}: {msg.content}" 
                                for msg in chat_history_msgs[-4:]
                            ])
                            
                            condense_prompt = f"""Given the following conversation and the user's new input, rephrase the new input into a standalone question containing all necessary context. 
If the new input is already standalone, leave it as is. Do NOT answer it, just reformulate it for a vector database search.

Chat History:
{chat_history_str}

New Input: {combined_user_input}
Standalone Question:"""
                            
                            try:
                                standalone_result = llm.invoke([{"role": "user", "content": condense_prompt}])
                                search_query = standalone_result.content.strip()
                            except Exception as e:
                                print(f"Condense question failed: {e}")

                        try:
                            source_docs = retriever.invoke(search_query)
                        except Exception as e:
                            st.error(f"ارتباط با سرور برای جستجوی داکیومنت قطع شد: {e}")
                            st.stop()

                        context_parts = []
                        for i, doc in enumerate(source_docs):
                            page_num = doc.metadata.get('page', 0) + 1 
                            source_name = os.path.basename(doc.metadata.get('source', f'Document_{i+1}'))
                            context_parts.append(f"--- Source: {source_name} (Page {page_num}) ---\n{doc.page_content}")
                        context_text = "\n\n".join(context_parts)
                        
                        system_prompt = f"""You are an expert Aviation AI Assistant.
Use the following pieces of retrieved context to answer the user's question. 

IMPORTANT INSTRUCTIONS:
1. You MUST answer entirely in ENGLISH.
2. If the answer is not found in the provided Context, you MUST start your response with the tag `[NO_INFO]` and then state that you cannot find the answer based on the documents.
3. You MUST cite your sources using EXACTLY the document name and page numbers provided in the context below (e.g., [Manual.pdf, Page 8]).
4. If an image or map is provided, analyze it carefully along with the text context.
5. Base your technical facts ONLY on the provided Context.
6. SAFETY DISCLAIMER: At the end of your response, always include a brief disclaimer that this is AI-generated and a certified mechanic must verify the action.

Context:
{context_text}

Question: {final_prompt}
Helpful Answer in English:"""

                    message_content = [{"type": "text", "text": system_prompt}]
                    
                    if uploaded_image and base64_image:
                        message_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                    
                    human_msg = HumanMessage(content=message_content)
                    
                    if is_trivial and not uploaded_image:
                        messages_to_send = [human_msg]
                    else:
                        messages_to_send = memory.chat_memory.messages + [human_msg]
                    
                    try:
                        result = llm.invoke(messages_to_send)
                        answer = result.content
                    except Exception as e:
                        st.error(f"Server is not responding (LLM API Error): {e}")
                        st.stop()
                    
                    is_answer_found_in_sources = True
                    if "[NO_INFO]" in answer:
                        is_answer_found_in_sources = False
                        answer = answer.replace("[NO_INFO]", "").strip()

                    # نمایش موقت متن قبل از رفرش صفحه
                    st.markdown(answer)
                    
                    # استخراج منابع برای ذخیره موقت
                    sources_list = []
                    if source_docs and len(source_docs) > 0 and is_answer_found_in_sources:
                        for i, doc in enumerate(source_docs):
                            sources_list.append({
                                "source": os.path.basename(doc.metadata.get('source', f'Source {i+1}')),
                                "page": doc.metadata.get('page', 0),
                                "content": doc.page_content
                            })

            if not is_trivial or uploaded_image:
                memory.save_context({"question": final_prompt}, {"answer": answer})
                
            auth.save_message(st.session_state.current_chat_id, "assistant", answer)
            
            # --- [تغییرات کلیدی برای حل مشکل گم شدن کلیدها] ---
            
            # ذخیره منابع آخرین پیام در نشست فعلی تا بعد از Refresh حفظ شود
            st.session_state.latest_sources[st.session_state.current_chat_id] = sources_list
            
            # ریست کردن وضعیت دکمه‌های آپلود
            st.session_state.file_uploader_key += 1
            
            # اعمال Refresh اجباری؛ این کار باعث می‌شود دکمه‌های Edit/Attach دوباره 
            # در پایین‌ترین بخش فرم و آپدیت‌شده رسم شوند (و چون در حلقه بالا دکمه کپی 
            # قرار داده شده، پیام‌های جدید نیز بلافاصله با دکمه کپی نمایش داده می‌شوند)
            st.rerun()
