"""
CodePilot AI — Streamlit Application

This is the entry point for the Streamlit UI. It orchestrates the user workflow:
Input → Clone → Analyze → Load → Chunk → Symbol Graph → Embed → Index → Hybrid Retrieval → RAG Chat → AI Software Engineer Tools
"""

from pathlib import Path
import streamlit as st

from backend.config import PARSEABLE_LANGUAGES
from backend.github_loader import clone_repository, validate_github_url
from backend.repository_analyzer import analyze_repository
from backend.file_loader import load_files
from backend.parsers.parser_factory import get_parser, get_supported_languages
from backend.chunker import chunk_repository
from backend.embedding import embed_chunks, embed_query, DEFAULT_EMBEDDING_MODEL
from backend.vector_store import FAISSVectorStore
from backend.retriever import HybridRetriever
from backend.llm import OllamaLLM, DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_BASE_URL
from backend.rag import RepositoryRAG, RAGResponse
from backend.graph import build_symbol_graph, SymbolGraph
from backend.ai_engineer import AIEngineerService


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CodePilot AI",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "repo_path" not in st.session_state:
    st.session_state.repo_path = None
if "repo_info" not in st.session_state:
    st.session_state.repo_info = None
if "source_files" not in st.session_state:
    st.session_state.source_files = None
if "code_chunks" not in st.session_state:
    st.session_state.code_chunks = None
if "symbol_graph" not in st.session_state:
    st.session_state.symbol_graph = None
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🧭 CodePilot AI")
    st.caption("AI-powered code intelligence")
    st.divider()

    st.subheader("Repository Input")
    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/user/repository",
    )

    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("🔍 Analyze Repository", use_container_width=True)
    with col2:
        clear_btn = st.button("🗑️ Clear", use_container_width=True)

    if clear_btn:
        st.session_state.repo_path = None
        st.session_state.repo_info = None
        st.session_state.source_files = None
        st.session_state.code_chunks = None
        st.session_state.symbol_graph = None
        st.session_state.vector_store = None
        st.session_state.chat_history = []
        st.rerun()

    st.divider()
    st.subheader("⚙️ LLM Configuration (Ollama)")

    ollama_url = st.text_input("Ollama Base URL", value=DEFAULT_OLLAMA_BASE_URL)
    ollama_model = st.text_input("Ollama Model", value=DEFAULT_OLLAMA_MODEL)

    if st.button("🔌 Test LLM Connection", use_container_width=True):
        llm_tester = OllamaLLM(base_url=ollama_url, model=ollama_model)
        is_ok, msg = llm_tester.test_connection()
        if is_ok:
            st.success(msg)
        else:
            st.warning(msg)

    st.divider()
    st.subheader("Capabilities")
    st.write("✅ GitHub Repo Cloning")
    st.write("✅ Repository Analysis")
    st.write("✅ Tree-sitter Parsing")
    st.write("✅ Symbol Knowledge Graph")
    st.write("✅ Change Impact Analysis")
    st.write("✅ FAISS Vector Indexing")
    st.write("✅ Hybrid RRF Retrieval")
    st.write("✅ Grounded RAG Chat")
    st.write("✅ AI Software Engineer Studio")

# ---------------------------------------------------------------------------
# Main: clone → analyze → load → chunk → symbol graph
# ---------------------------------------------------------------------------

if analyze_btn and repo_url:
    if not validate_github_url(repo_url):
        st.error("❌ Invalid GitHub URL. Expected: `https://github.com/user/repository`")
    else:
        with st.status("🔄 Processing repository...", expanded=True) as status:
            st.write("📥 Cloning repository...")
            try:
                repo_path = clone_repository(repo_url)
                st.session_state.repo_path = repo_path
                st.write(f"✅ Cloned to `{repo_path}`")
            except Exception as e:
                st.error(f"❌ Clone failed: {e}")
                st.stop()

            st.write("📊 Analyzing repository...")
            try:
                repo_info = analyze_repository(repo_path)
                st.session_state.repo_info = repo_info
                st.write(f"✅ Found {repo_info.total_files} files in {len(repo_info.languages)} languages")
            except Exception as e:
                st.error(f"❌ Analysis failed: {e}")
                st.stop()

            st.write("📂 Loading source files...")
            try:
                source_files = load_files(repo_path)
                st.session_state.source_files = source_files
                st.write(f"✅ Loaded {len(source_files)} source files")
            except Exception as e:
                st.error(f"❌ File loading failed: {e}")
                st.stop()

            st.write("🌳 Chunking source code (AST + Windowing)...")
            try:
                chunks = chunk_repository(source_files)
                st.session_state.code_chunks = chunks
                st.write(f"✅ Extracted {len(chunks)} code chunks")
            except Exception as e:
                st.error(f"❌ Chunking failed: {e}")
                st.stop()

            st.write("🕸️ Building Code Knowledge Graph & Dependencies...")
            try:
                symbol_graph = build_symbol_graph(chunks)
                st.session_state.symbol_graph = symbol_graph
                st.write(f"✅ Indexed {symbol_graph.total_nodes} nodes and {symbol_graph.total_edges} relationships")
            except Exception as e:
                st.error(f"❌ Graph building failed: {e}")
                st.stop()

            st.session_state.vector_store = None
            st.session_state.chat_history = []

            status.update(label="✅ Repository processed successfully!", state="complete")

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

if st.session_state.repo_info:
    repo_info = st.session_state.repo_info

    st.header(f"📊 {repo_info.name}")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", repo_info.total_files)
    with col2:
        st.metric("Primary Language", repo_info.primary_language)
    with col3:
        st.metric("Languages", len(repo_info.languages))
    with col4:
        size_mb = repo_info.total_size_bytes / (1024 * 1024)
        st.metric("Total Size", f"{size_mb:.2f} MB")

    st.divider()

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📝 Language Distribution")
        if repo_info.languages:
            import pandas as pd
            lang_df = pd.DataFrame(
                list(repo_info.languages.items()),
                columns=["Language", "Files"],
            )
            st.dataframe(lang_df, use_container_width=True, hide_index=True)
        else:
            st.info("No recognized languages found.")

    with col_right:
        st.subheader("📁 Folder Structure")
        if repo_info.folders:
            display_folders = repo_info.folders[:30]
            for folder in display_folders:
                st.text(f"📂 {folder}")
            if len(repo_info.folders) > 30:
                st.caption(f"... and {len(repo_info.folders) - 30} more folders")
        else:
            st.info("No subfolders found.")

    st.divider()

# ---------------------------------------------------------------------------
# Phase 7: AI Software Engineer Studio
# ---------------------------------------------------------------------------

if st.session_state.code_chunks is not None:
    chunks = st.session_state.code_chunks
    symbol_graph = st.session_state.symbol_graph

    retriever = HybridRetriever(
        vector_store=st.session_state.vector_store,
        chunks=chunks,
        symbol_graph=symbol_graph,
    )
    llm_client = OllamaLLM(base_url=ollama_url, model=ollama_model)
    rag_pipeline = RepositoryRAG(retriever=retriever, symbol_graph=symbol_graph, llm=llm_client)
    ai_engineer = AIEngineerService(rag=rag_pipeline, symbol_graph=symbol_graph, llm=llm_client)

    st.header("🛠️ AI Software Engineer Studio")

    studio_tab1, studio_tab2, studio_tab3 = st.tabs([
        "📖 Code Explanation",
        "🧐 LLM Code Review",
        "📝 Documentation Generator",
    ])

    # Tab 1: Code Explanation
    with studio_tab1:
        st.subheader("📖 Structural Code Explanation")
        st.caption("Select a symbol to generate a grounded explanation with line range citations and caller map.")

        symbol_options = sorted(list(set([c.qualified_name for c in chunks])))
        if symbol_options:
            selected_sym = st.selectbox("Select symbol to explain:", options=symbol_options, key="exp_sym_select")

            if st.button("Generate Explanation", type="primary", key="explain_btn"):
                with st.spinner("Analyzing code structure and generating explanation..."):
                    res = ai_engineer.explain_symbol(selected_sym, chunks)

                st.markdown(f"### Explanation: `{res['symbol_name']}`")
                st.caption(f"Location: `{res.get('file_path')}:{res.get('line_range')}`")

                if res.get("callers"):
                    st.write(f"📥 **Callers:** {', '.join([f'`{c}`' for c in res['callers']])}")
                if res.get("callees"):
                    st.write(f"📤 **Callees:** {', '.join([f'`{c}`' for c in res['callees']])}")

                st.markdown(res["explanation"])

                if res.get("code"):
                    with st.expander("Show Code Snippet"):
                        st.code(res["code"])

    # Tab 2: Code Review Assistant
    with studio_tab2:
        st.subheader("🧐 LLM-Assisted Code Review")
        st.caption("Note: LLM-assisted code review evaluates modularity, readability, and error handling based on code context and AST structure. It complements deterministic static analysis tools.")

        file_options = sorted(list(set([c.relative_path for c in chunks])))
        if file_options:
            selected_file = st.selectbox("Select file to review:", options=file_options, key="review_file_select")

            if st.button("Run Code Review", type="primary", key="review_btn"):
                with st.spinner("Reviewing file structure and context..."):
                    res = ai_engineer.review_code(selected_file, chunks)

                st.markdown(f"### Code Review Report: `{res['file_path']}`")
                st.markdown(res["review"])

    # Tab 3: Documentation Generator
    with studio_tab3:
        st.subheader("📝 Automated Documentation Generator")
        st.caption("Generate publication-ready Markdown documentation derived from repository metadata, CodeChunks, and SymbolGraph.")

        doc_kind = st.radio(
            "Select documentation type:",
            options=["README.md", "Architecture Overview", "API & Module Reference"],
            horizontal=True,
        )

        doc_type_map = {
            "README.md": "readme",
            "Architecture Overview": "architecture",
            "API & Module Reference": "api",
        }

        if st.button("Generate Document", type="primary", key="doc_gen_btn"):
            with st.spinner(f"Generating {doc_kind}..."):
                res = ai_engineer.generate_documentation(
                    doc_type=doc_type_map[doc_kind],
                    repo_info=st.session_state.repo_info,
                    chunks=chunks,
                )

            st.markdown(f"### {res['title']}")
            st.markdown(res["content"])

            st.download_button(
                label=f"📥 Download {res['title']}",
                data=res["content"],
                file_name=f"{doc_type_map[doc_kind]}.md",
                mime="text/markdown",
            )

    st.divider()

# ---------------------------------------------------------------------------
# Phase 5: Code Intelligence & Dependency Graph Dashboard
# ---------------------------------------------------------------------------

if st.session_state.symbol_graph is not None:
    graph = st.session_state.symbol_graph

    st.header("🕸️ Code Intelligence & Dependency Graph")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Symbol Graph Nodes", graph.total_nodes)
    with col2:
        st.metric("Relationships Tracked", graph.total_edges)

    st.caption("Heuristic relationship tracking (contains, extends, implements, imports, calls, uses).")

    tab1, tab2 = st.tabs(["🔍 Symbol & Caller Inspector", "💥 Change Impact Analysis"])

    with tab1:
        all_symbol_keys = sorted(list(graph.nodes.keys()))
        if all_symbol_keys:
            selected_symbol = st.selectbox("Select a symbol to inspect:", options=all_symbol_keys)
            if selected_symbol:
                node = graph.nodes[selected_symbol]
                st.markdown(f"### `{node.qualified_name}` ({node.chunk_type})")
                st.caption(f"File: `{node.relative_path}` | Lines: `{node.start_line}–{node.end_line}` | Language: `{node.language}`")

                col_callers, col_callees = st.columns(2)

                with col_callers:
                    st.subheader("📥 Callers (called_by)")
                    callers = graph.get_callers(selected_symbol)
                    if callers:
                        for c_node, rel in callers:
                            st.write(f"• `{c_node.qualified_name}` (`{c_node.relative_path}:{c_node.start_line}`)")
                    else:
                        st.info("No callers detected.")

                with col_callees:
                    st.subheader("📤 Callees & Outgoing Dependencies")
                    deps = graph.get_dependencies(selected_symbol)
                    if deps:
                        for target_node, rel_type in deps:
                            st.write(f"• **[{rel_type}]** `{target_node.qualified_name}` (`{target_node.relative_path}`)")
                    else:
                        st.info("No outgoing dependencies detected.")
        else:
            st.info("No symbols indexed in graph.")

    with tab2:
        st.subheader("💥 Change Impact Analysis")
        st.caption("Recursively traces all symbols and files dependent on a target symbol.")
        if all_symbol_keys:
            impact_target = st.selectbox("Select target symbol for impact analysis:", options=all_symbol_keys, key="impact_select")
            if impact_target and st.button("Run Impact Analysis", type="primary"):
                impacts = graph.get_impact_analysis(impact_target)
                if impacts:
                    st.warning(f"⚠️ Changing `{impact_target}` potentially impacts {len(impacts)} code units:")
                    import pandas as pd
                    impact_df = pd.DataFrame(impacts)[["qualified_name", "chunk_type", "relative_path", "line_range", "depth", "relation_type"]]
                    st.dataframe(impact_df, use_container_width=True, hide_index=True)
                else:
                    st.success(f"✅ No downstream dependent symbols detected for `{impact_target}`.")

    st.divider()

# ---------------------------------------------------------------------------
# Phase 3: Semantic Indexing Controls
# ---------------------------------------------------------------------------

if st.session_state.code_chunks is not None:
    chunks = st.session_state.code_chunks

    st.header("⚡ Semantic Indexing (FAISS + BGE-M3)")

    col_btn, col_info = st.columns([1, 2])

    with col_btn:
        build_index_btn = st.button("🚀 Build FAISS Index", type="primary", use_container_width=True)

    if build_index_btn:
        with st.spinner("Embedding code chunks with BGE-M3 and building FAISS index..."):
            try:
                embeddings = embed_chunks(chunks, show_progress=False)

                vector_store = FAISSVectorStore(dimension=embeddings.shape[1])
                vector_store.add_chunks(chunks, embeddings)

                vector_db_dir = Path("vector_db") / repo_info.name
                vector_store.save(str(vector_db_dir))

                st.session_state.vector_store = vector_store
                st.success(f"✅ Vector index built! {vector_store.total_vectors} vectors ({vector_store.dimension} dimensions)")
            except Exception as e:
                st.error(f"❌ Indexing failed: {e}")

    if st.session_state.vector_store is not None:
        vs = st.session_state.vector_store
        st.info(f"🟢 **Index Active:** {vs.total_vectors} chunks indexed | Dimension: {vs.dimension} | Model: `{DEFAULT_EMBEDDING_MODEL}`")

    st.divider()

# ---------------------------------------------------------------------------
# Phase 4: Repository Chat & Grounded RAG
# ---------------------------------------------------------------------------

if st.session_state.code_chunks is not None:
    st.header("💬 Repository Chat (Grounded RAG)")
    st.caption("Ask questions about the repository. Answers are strictly grounded in retrieved source code and relationship graph evidence.")

    retriever = HybridRetriever(
        vector_store=st.session_state.vector_store,
        chunks=st.session_state.code_chunks,
        symbol_graph=st.session_state.symbol_graph,
    )
    llm_client = OllamaLLM(base_url=ollama_url, model=ollama_model)
    rag_pipeline = RepositoryRAG(
        retriever=retriever,
        symbol_graph=st.session_state.symbol_graph,
        llm=llm_client,
    )

    for user_msg, rag_resp in st.session_state.chat_history:
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            st.markdown(rag_resp.answer)
            if rag_resp.cited_sources:
                st.caption(f"📍 **Cited Sources:** {', '.join([f'`{src}`' for src in rag_resp.cited_sources])}")
            if rag_resp.retrieved_chunks:
                with st.expander("📚 Retrieved Source Code Evidence", expanded=False):
                    for rank, (chunk, score) in enumerate(rag_resp.retrieved_chunks, 1):
                        st.markdown(f"**Chunk #{rank}** | `{chunk.relative_path}:{chunk.start_line}-{chunk.end_line}` | Score: `{score:.4f}`")
                        st.code(chunk.code, language=chunk.language.lower())

    user_query = st.chat_input("Ask a question about authentication, callers of X, architecture, etc...")

    if user_query:
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Retrieving repository evidence and generating grounded response..."):
                rag_resp = rag_pipeline.ask(user_query, top_k=5, llm_model=ollama_model)

            st.markdown(rag_resp.answer)

            if rag_resp.cited_sources:
                st.caption(f"📍 **Cited Sources:** {', '.join([f'`{src}`' for src in rag_resp.cited_sources])}")

            if rag_resp.retrieved_chunks:
                with st.expander("📚 Retrieved Source Code Evidence", expanded=False):
                    for rank, (chunk, score) in enumerate(rag_resp.retrieved_chunks, 1):
                        st.markdown(f"**Chunk #{rank}** | `{chunk.relative_path}:{chunk.start_line}-{chunk.end_line}` | Score: `{score:.4f}`")
                        st.code(chunk.code, language=chunk.language.lower())

        st.session_state.chat_history.append((user_query, rag_resp))

    st.divider()

# ---------------------------------------------------------------------------
# Parsed Code Structure View
# ---------------------------------------------------------------------------

if st.session_state.code_chunks is not None:
    chunks = st.session_state.code_chunks

    st.header("🌳 Parsed Code Chunks")

    if not chunks:
        st.info("No code chunks extracted.")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        chunk_types = {}
        for c in chunks:
            chunk_types[c.chunk_type] = chunk_types.get(c.chunk_type, 0) + 1

        with col1:
            st.metric("Total Chunks", len(chunks))
        with col2:
            st.metric("Classes", chunk_types.get("class", 0) + chunk_types.get("interface", 0))
        with col3:
            st.metric("Functions", chunk_types.get("function", 0))
        with col4:
            st.metric("Methods", chunk_types.get("method", 0))
        with col5:
            st.metric("Blocks (Fallback)", chunk_types.get("block", 0))

        all_types = sorted(set(c.chunk_type for c in chunks))
        selected_types = st.multiselect(
            "Filter chunks by type",
            options=all_types,
            default=all_types,
        )

        filtered_chunks = [c for c in chunks if c.chunk_type in selected_types]

        files = {}
        for c in filtered_chunks:
            if c.relative_path not in files:
                files[c.relative_path] = []
            files[c.relative_path].append(c)

        for file_path, file_chunks in sorted(files.items()):
            with st.expander(f"📄 {file_path} ({len(file_chunks)} chunks)", expanded=False):
                for chunk in file_chunks:
                    st.markdown(
                        f"**{chunk.chunk_type}** `{chunk.qualified_name}` "
                        f"(lines {chunk.start_line}–{chunk.end_line})"
                    )
                    st.code(chunk.code, language=chunk.language.lower())
                    st.markdown("---")

# ---------------------------------------------------------------------------
# Welcome state (no repo loaded)
# ---------------------------------------------------------------------------

if st.session_state.repo_info is None:
    st.title("🧭 CodePilot AI")
    st.subheader("AI-Powered Code Intelligence Platform")
    st.markdown(
        """
        **CodePilot AI** ingests GitHub repositories, parses their structure using
        Tree-sitter AST, constructs an in-memory Code Knowledge Graph, generates BGE-M3 embeddings,
        and provides grounded developer assistance tools using Ollama.

        ### Getting Started

        1. Paste a **public GitHub repository URL** in the sidebar.
        2. Click **Analyze Repository**.
        3. Use the **AI Software Engineer Studio** for explanations, code reviews, and docs generation.
        4. Explore the **Code Intelligence & Dependency Graph**.
        5. Click **Build FAISS Index** to enable vector similarity search.
        6. Chat with your repository in the **Repository Chat** interface!
        """
    )
