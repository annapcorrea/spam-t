import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

st.title('Welcome to SPAM-T')
st.write('Easily report Spams')

# Function to send OTP
def send_otp(phone_number, first_name, last_name, email):
    try:
        response = requests.post(
            "https://api.staging.v2.tnid.com/auth/create_user_otp",
            json={
                "telephone_number": phone_number,
                "first_name": first_name,
                "last_name": last_name,
                "email": email
            }
        )
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {e}")
        return None

# Function to verify OTP and get access token
def verify_otp(phone_number, otp_code):
    try:
        response = requests.post(
            "https://api.staging.v2.tnid.com/auth/token",
            json={
                "telephone_number": phone_number,
                "otp_code": otp_code
            }
        )
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {e}")
        return None

# Define GraphQL client
def create_client(token, endpoint):
    transport = AIOHTTPTransport(url=endpoint, headers={"Authorization": f"Bearer {token}"})
    return Client(transport=transport, fetch_schema_from_transport=True)

# Function to create a spam report
def create_spam_report(client, from_number, to_number, channel_type, message_content):
    mutation = gql(
        """
        mutation CreateSpamReport(
            $fromNumber: String!,
            $toNumber: String!,
            $channelType: SpamReportChannelType!,
            $timestamp: NaiveDateTime!,
            $messageContent: String!
        ) {
            createSpamReport(
                fromNumber: $fromNumber,
                toNumber: $toNumber,
                channelType: $channelType,
                timestamp: $timestamp,
                messageContent: $messageContent
            ) {
                id
                fromNumber
                toNumber
                status
                messageContent
            }
        }
        """
    )
    timestamp = datetime.now().isoformat()
    params = {
        "fromNumber": from_number,
        "toNumber": to_number,
        "channelType": channel_type,
        "timestamp": timestamp,
        "messageContent": message_content
    }
    return client.execute(mutation, variable_values=params)

# Function to fetch spam reports
def fetch_spam_reports(client):
    query = gql(
        """
        query GetSpamReports {
            spamReports {
                id
                fromNumber
                toNumber
                channelType
                timestamp
                messageContent
                status
            }
        }
        """
    )
    return client.execute(query)

# Step 1: OTP request form
with st.form("otp_form"):
    st.write("Enter your details to get a One-Time Password (OTP)")
    phone_number = st.text_input("Phone Number (Including Country Code)")
    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    email = st.text_input("Email")
    send_otp_btn = st.form_submit_button('Send OTP')

if send_otp_btn:
    if not phone_number or not first_name or not last_name or not email:
        st.error("Please fill in all fields.")
    else:
        response = send_otp(phone_number, first_name, last_name, email)
        if response and response.status_code == 200:
            st.success("OTP sent successfully! Check your phone.")
        else:
            error_message = response.json().get("error", "An error occurred.") if response else "No response"
            st.error(f"Failed to send OTP: {error_message}")

# Step 2: OTP verification form
with st.form("otp_verification_form"):
    st.write("Enter the OTP you received on your phone")
    otp_code = st.text_input("OTP Code")
    verify_otp_btn = st.form_submit_button('Verify OTP')

if verify_otp_btn:
    response = verify_otp(phone_number, otp_code)
    if response and response.status_code == 200:
        token = response.json().get('access_token')
        st.session_state['token'] = token
        st.success("OTP verified! You are now logged in.")
    else:
        st.error("Failed to verify OTP. Try again.")

# If user is authenticated, provide additional API functionality
if 'token' in st.session_state:
    token = st.session_state['token']
    client = create_client(token, "https://api.staging.v2.tnid.com/user")

    # Viewing Spam Reports
    st.write("### Your Spam Reports")

    spam_reports = fetch_spam_reports(client)

    # Search Functionality
    search_term = st.text_input("Search Spam Reports", "")
    
    if spam_reports:
        filtered_reports = [
            report for report in spam_reports['spamReports']
            if search_term.lower() in report['fromNumber'].lower() or
               search_term.lower() in report['messageContent'].lower()
        ]

        if filtered_reports:
            for report in filtered_reports:
                st.write(f"**Report ID:** {report['id']}")
                st.write(f"**From:** {report['fromNumber']}")
                st.write(f"**To:** {report['toNumber']}")
                st.write(f"**Channel Type:** {report['channelType']}")
                st.write(f"**Timestamp:** {report['timestamp']}")
                st.write(f"**Message Content:** {report['messageContent']}")
                st.write(f"**Status:** {report['status']}")
                st.markdown("---")
        else:
            st.write("No matching reports found.")

    else:
        st.write("No spam reports found.")

    # Data Visualization: Count of Spam Reports by Channel Type
    if spam_reports:
        channel_counts = {}
        for report in spam_reports['spamReports']:
            channel = report['channelType']
            if channel in channel_counts:
                channel_counts[channel] += 1
            else:
                channel_counts[channel] = 1
        
        # Create a DataFrame for Plotly
        df_channel_counts = pd.DataFrame(list(channel_counts.items()), columns=['Channel Type', 'Count'])
        
        # Plotting with Plotly
        fig = px.bar(df_channel_counts, x='Channel Type', y='Count', title='Spam Reports by Channel Type')
        st.plotly_chart(fig, use_container_width=True)

    # Export Function
    if spam_reports:
        df = pd.DataFrame(spam_reports['spamReports'])
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download Spam Reports as CSV",
            data=csv,
            file_name='spam_reports.csv',
            mime='text/csv'
        )

    # Import Function
    uploaded_file = st.file_uploader("Upload Spam Reports CSV", type=["csv"])
    
    if uploaded_file is not None:
        try:
            imported_data = pd.read_csv(uploaded_file)
            # Process the imported data (e.g., save it to the backend)
            st.success("Spam reports imported successfully!")
        except Exception as e:
            st.error(f"An error occurred while importing: {e}")

    # Create Spam Report
    st.write("#### Create a Spam Report")
    from_number = st.text_input("From Phone Number")
    to_number = st.text_input("To Phone Number")
    channel_type = st.selectbox("Channel Type", ["SMS", "EMAIL", "VOICE"])
    message_content = st.text_area("Message Content")

    if st.button("Report Spam"):
        result = create_spam_report(client, from_number, to_number, channel_type, message_content)
        st.write("Spam Report Created:", result)
