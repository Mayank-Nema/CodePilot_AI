import streamlit as st
from Backend.github_loader import GitHubLoader
from Backend.repository_analyzer import RepositoryAnalyzer

st.set_page_config(
    page_title="CodePilot AI",
    layout="wide"
)

st.title("🚀 CodePilot AI")

st.write("AI Software Engineering Assistant")

repo_url = st.text_input("GitHub Repository URL (HTTPS or SSH)")

if st.button("Analyze Repository"):

    if repo_url.strip() == "":
        st.error("Please enter a GitHub URL.")

    else:

        loader = GitHubLoader()

        with st.spinner("Cloning repository..."):

            try:
                path = loader.clone_repo(repo_url)
                analyzer = RepositoryAnalyzer()
                info = analyzer.analyze(path)

                st.subheader("Repository Information")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Repository", info["repo_name"])

                with col2:
                    st.metric("Main Language", info["main_language"])

                with col3:
                    st.metric("Total Files", info["total_files"])

                st.subheader("Languages Used")
                st.json(info["languages"])

                st.subheader("Largest File")
                st.write(info["largest_file"])
                st.write(f"{info['largest_size_kb']} KB")

                st.subheader("Folders")
                st.write(info["folders"])
                st.success("Repository cloned successfully!")

            except Exception as e:
             st.error(str(e))