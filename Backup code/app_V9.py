import sys
import os
import json
import base64
from openai import OpenAI
import streamlit as st
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

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ''
if 'current_chat_id' not in st.session_state:
    st.session_state.current_chat_id = None
if 'file_uploader_key' not in st.session_state:
    st.session_state.file_uploader_key = 0

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
    
    # --- استفاده از os.environ به جای st.secrets برای داکر ---
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    BASE_URL = os.environ.get("BASE_URL")
    
    if not OPENAI_API_KEY or not BASE_URL:
        st.error("FATAL ERROR: `OPENAI_API_KEY` or `BASE_URL` not found in environment variables. Please check your .env file.")
        print(">>> ERROR: Secrets not found. Stopping execution.")
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

    for msg in db_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and len(msg.get("sources", [])) > 0:
                with st.expander("📑 Sources Used"):
                    for i, doc_dict in enumerate(msg["sources"]):
                        page_number = doc_dict.get('page', 0) + 1
                        source_name = doc_dict.get('source', f'Source {i+1}')
                        st.write(f"**Source: {source_name} (Page {page_number}):**")
                        st.write(doc_dict.get('content', ''))


    is_current_archived = any(c[0] == st.session_state.current_chat_id for c in archived_chats)
    
    if is_current_archived:
        st.warning("این چت آرشیو شده است و فقط قابل خواندن میباشد.")
    else:
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
        
        if text_prompt:
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
                    
                    # -------------------------------------------------------------
                    # ۰. پردازش اولیه تصویر برای موتور جستجو (Vision-to-Text)
                    # -------------------------------------------------------------
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

                    # --- [اضافه شده] بررسی اینکه آیا پیام صرفاً احوال‌پرسی است یا خیر ---
                    trivial_phrases = ["hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "good morning", "good afternoon"]
                    is_trivial = final_prompt.strip().lower() in trivial_phrases
                    
                    source_docs = []
                    context_text = ""
                    
                    # اگر پیام فقط یک سلام/تشکر ساده بود و عکسی هم ضمیمه نشده بود، جستجو را دور بزن
                    if is_trivial and not uploaded_image:
                        system_prompt = "You are an expert Aviation AI Assistant. The user just greeted you or said thanks. Reply politely and briefly, asking how you can help them with aviation or aircraft maintenance today."
                    
                    else:
                        # -------------------------------------------------------------
                        # ۱. افزودن حافظه به موتور جستجو (Condense Question)
                        # -------------------------------------------------------------
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

                        # -------------------------------------------------------------
                        # ۲. جستجو در دیتابیس با استفاده از سوال کامل شده
                        # -------------------------------------------------------------
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
                        
                        # -------------------------------------------------------------
                        # ۳. پرامپت نهایی با قوانین سخت‌گیرانه و سلب مسئولیت
                        # -------------------------------------------------------------
                        # ... (کد شما)
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

                    
                                        # -------------------------------------------------------------
                    # Send to the language model to generate the final answer (common for both cases)
                    # -------------------------------------------------------------
                    message_content = [{"type": "text", "text": system_prompt}]
                    
                    if uploaded_image and base64_image:
                        message_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                    
                    human_msg = HumanMessage(content=message_content)
                    
                    # If the message is trivial, there's no need to send the entire history to avoid hallucinations
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
                    
                    # --- [بخش جدید: کنترل نمایش منابع بر اساس تگ] ---
                    is_answer_found_in_sources = True
                    if "[NO_INFO]" in answer:
                        is_answer_found_in_sources = False
                        # حذف تگ از متن تا کاربر آن را نبیند
                        answer = answer.replace("[NO_INFO]", "").strip()

                    # 1. Display the text answer (without the tag)
                    st.markdown(answer)
                    
                    # 2. Prepare and display the sources box (only for the current UI render)
                    sources_list = []
                    # شرط is_answer_found_in_sources اضافه شد تا منابع فقط در صورت مرتبط بودن نمایش داده شوند
                    if source_docs and len(source_docs) > 0 and is_answer_found_in_sources:
                        with st.expander("📑 Sources Used"):

                            for i, doc in enumerate(source_docs):
                                page_num = doc.metadata.get('page', 0) + 1 
                                source_name = os.path.basename(doc.metadata.get('source', f'Source {i+1}'))
                                content = doc.page_content
                                
                                # Display to the user
                                st.write(f"**Source {i+1}: {source_name} (Page {page_num}):**")
                                st.info(content)
                                
                                # Save in a list (useful if you plan to save them in the database later)
                                sources_list.append({
                                    "source": source_name,
                                    "page": doc.metadata.get('page', 0),
                                    "content": content
                                })

            # 3. Update memory (Langchain Memory) for use in subsequent follow-up questions
            if not is_trivial or uploaded_image:
                memory.save_context({"question": final_prompt}, {"answer": answer})
                
            # 4. Save to your database (auth.save_message function)
            # Important: Since your function currently only accepts text, we are not saving the sources 
            # as JSON in your database (unless you have updated it).
            # For now, only the text is saved to prevent the app from crashing.
            auth.save_message(st.session_state.current_chat_id, "assistant", answer)
            
            # Change the uploader key to reset the voice and image upload elements
            st.session_state.file_uploader_key += 1


