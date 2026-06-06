import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_connection
from datetime import date

st.set_page_config(
    page_title="Sales Management Dashboard",
    layout="wide"
)

# =========================
# LOGIN FUNCTION
# =========================
def login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, role, branch_id
        FROM users
        WHERE username=%s
        AND password=%s
        """,
        (username, password)
    )
    user = cursor.fetchone()
    conn.close()
    return user


# =========================
# SESSION STATE
# =========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = ""

if "branch_id" not in st.session_state:
    st.session_state.branch_id = None


# =========================
# LOGIN SCREEN
# =========================
if not st.session_state.logged_in:
    st.title("Sales Management Dashboard")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.username = user[0]
            st.session_state.role = user[1]
            st.session_state.branch_id = user[2]
            st.rerun()
        else:
            st.error("Invalid Username or Password")


# =========================
# MAIN APPLICATION
# =========================
else:
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    st.sidebar.write(f"Role : {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.session_state.branch_id = None
        st.rerun()

    conn = get_connection()
    st.title("Sales Management Dashboard")

    # =========================
    # LOAD GLOBAL BRANCHES REFERENCE
    # =========================
    branches_df = pd.read_sql(
        """
        SELECT branch_id, branch_name
        FROM branches
        ORDER BY branch_name
        """,
        conn
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Dashboard",
            "Sales Entry",
            "Payment Entry",
            "Queries"
        ]
    )

    # =========================
    # DASHBOARD TAB
    # =========================
    with tab1:
        st.subheader("Customer Sales Data")

        col1, col2 = st.columns(2)

        with col1:
            if st.session_state.role == "Super Admin":
                branch_options = ["All Branches"] + list(branches_df["branch_name"])
                selected_branch = st.selectbox("Filter by Branch", branch_options, key="global_branch_filter")
            else:
                admin_branch_df = branches_df[
                    branches_df["branch_id"] == st.session_state.branch_id
                ]
                selected_branch = admin_branch_df["branch_name"].iloc[0]
                st.text_input("Branch", value=selected_branch, disabled=True, key="global_branch_locked")

        with col2:
            product_df = pd.read_sql(
                """
                SELECT DISTINCT product_name
                FROM customer_sales
                WHERE product_name IS NOT NULL AND product_name != ''
                ORDER BY product_name
                """,
                conn
            )
            product_options = ["All Products"] + list(product_df["product_name"])
            selected_product = st.selectbox("Filter by Product", product_options, key="global_product_filter")

        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("Start Date", value=date(2024, 1, 1), key="global_start_date")
        with col4:
            end_date = st.date_input("End Date", value=date.today(), key="global_end_date")

        branch_condition = ""
        if st.session_state.role != "Super Admin":
            branch_condition = f"AND cs.branch_id = {st.session_state.branch_id}"
        elif selected_branch != "All Branches":
            selected_branch_id = int(
                branches_df[
                    branches_df["branch_name"] == selected_branch
                ]["branch_id"].iloc[0]
            )
            branch_condition = f"AND cs.branch_id = {selected_branch_id}"

        product_condition = ""
        if selected_product != "All Products":
            product_condition = f"AND cs.product_name = '{selected_product}'"

        # Results Table
        st.markdown("---")
        report_query = f"""
        SELECT
            cs.sale_id,
            b.branch_name,
            cs.date,
            cs.name,
            cs.mobile_number,
            cs.product_name,
            cs.gross_sales,
            cs.received_amount,
            cs.pending_amount,
            cs.status
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id
        WHERE 1=1
        {branch_condition}
        {product_condition}
        AND cs.date >= '{start_date}'
        AND cs.date <= '{end_date}'
        ORDER BY cs.sale_id DESC
        """

        report_df = pd.read_sql(report_query, conn)
        st.dataframe(report_df, use_container_width=True)

        # Dashboard Summary
        st.markdown("---")
        st.subheader("Dashboard Summary")

        kpi_query = f"""
        SELECT
            SUM(gross_sales) AS total_sales,
            SUM(received_amount) AS total_received,
            SUM(pending_amount) AS total_pending,
            COUNT(*) AS total_records
        FROM customer_sales cs
        WHERE 1=1
        {branch_condition}
        {product_condition}
        AND cs.date >= '{start_date}'
        AND cs.date <= '{end_date}'
        """

        kpi_df = pd.read_sql(kpi_query, conn)

        total_sales = kpi_df["total_sales"][0] if pd.notna(kpi_df["total_sales"][0]) else 0
        total_received = kpi_df["total_received"][0] if pd.notna(kpi_df["total_received"][0]) else 0
        total_pending = kpi_df["total_pending"][0] if pd.notna(kpi_df["total_pending"][0]) else 0
        total_records = kpi_df["total_records"][0] if pd.notna(kpi_df["total_records"][0]) else 0

        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        col_kpi1.metric("Total Sales", f"₹ {total_sales:,.0f}")
        col_kpi2.metric("Total Received", f"₹ {total_received:,.0f}")
        col_kpi3.metric("Total Pending", f"₹ {total_pending:,.0f}")
        col_kpi4.metric("Sales Records", int(total_records))

        # Branch Wise Sales Graph
        st.markdown("---")
        st.subheader("Branch Wise Sales Performance")

        branch_chart_query = f"""
        SELECT
            b.branch_name,
            SUM(cs.gross_sales) AS total_sales
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id
        WHERE 1=1
        {branch_condition}
        {product_condition}
        AND cs.date >= '{start_date}'
        AND cs.date <= '{end_date}'
        GROUP BY b.branch_name
        ORDER BY total_sales DESC
        """

        branch_chart_df = pd.read_sql(branch_chart_query, conn)
        fig = px.bar(branch_chart_df, x="branch_name", y="total_sales")
        st.plotly_chart(fig, use_container_width=True)

        # Payment Method Summary
        st.markdown("---")
        st.subheader("Payment Method Summary")

        if st.session_state.role == "Super Admin":
            payment_branch_options = ["All Branches"] + list(branches_df["branch_name"])
            selected_payment_branch = st.selectbox(
                "Payment Summary Branch",
                payment_branch_options,
                key="payment_summary_branch_select"
            )

            if selected_payment_branch == "All Branches":
                payment_chart_query = """
                SELECT payment_method, SUM(amount_paid) AS total_amount
                FROM payment_splits
                GROUP BY payment_method
                """
            else:
                target_branch_id = int(
                    branches_df[branches_df["branch_name"] == selected_payment_branch]["branch_id"].iloc[0]
                )
                payment_chart_query = f"""
                SELECT ps.payment_method, SUM(ps.amount_paid) AS total_amount
                FROM payment_splits ps
                JOIN customer_sales cs ON ps.sale_id = cs.sale_id
                WHERE cs.branch_id = {target_branch_id}
                GROUP BY ps.payment_method
                """
        else:
            admin_branch_name = branches_df[
                branches_df["branch_id"] == st.session_state.branch_id
            ]["branch_name"].iloc[0]

            st.text_input("Branch", value=admin_branch_name, disabled=True, key="payment_summary_branch_lock")

            payment_chart_query = f"""
            SELECT ps.payment_method, SUM(ps.amount_paid) AS total_amount
            FROM payment_splits ps
            JOIN customer_sales cs ON ps.sale_id = cs.sale_id
            WHERE cs.branch_id = {st.session_state.branch_id}
            GROUP BY ps.payment_method
            """

        payment_chart_df = pd.read_sql(payment_chart_query, conn)
        fig2 = px.bar(payment_chart_df, x="payment_method", y="total_amount", title="Payment Method Summary")
        st.plotly_chart(fig2, use_container_width=True)


    # =========================
    # SALES ENTRY TAB
    # =========================
    with tab2:
        st.subheader("Add New Sale")

        branch_data = pd.read_sql("SELECT branch_id, branch_name FROM branches ORDER BY branch_name", conn)

        if st.session_state.role == "Super Admin":
            sale_branch = st.selectbox("Select Branch", branch_data["branch_name"], key="sale_branch")
        else:
            admin_branch_df = branch_data[branch_data["branch_id"] == st.session_state.branch_id]
            sale_branch = admin_branch_df["branch_name"].iloc[0]
            st.text_input("Branch", value=sale_branch, disabled=True, key="sale_branch_disabled")

        sale_date = st.date_input("Sale Date", value=date.today(), key="sale_date")
        customer_name = st.text_input("Customer Name", key="customer_name")
        mobile_number = st.text_input("Mobile Number", key="mobile_number")
        product_name = st.text_input("Product Name", key="product_name")
        gross_sales = st.number_input("Gross Sales Amount", min_value=0.0, value=0.0, step=100.0, key="gross_sales")
        status = st.selectbox("Status", ["Open", "Close"], key="status")

        if st.button("Add Sale"):
            try:
                selected_branch_id = int(
                    branch_data[branch_data["branch_name"] == sale_branch]["branch_id"].iloc[0]
                )
                cursor = conn.cursor()
                insert_query = """
                INSERT INTO customer_sales
                (branch_id, date, name, mobile_number, product_name, gross_sales, received_amount, status)
                VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
                """
                cursor.execute(
                    insert_query,
                    (selected_branch_id, sale_date, customer_name, mobile_number, product_name, gross_sales, status)
                )
                conn.commit()
                st.success("Sale Added Successfully!")
            except Exception as e:
                st.error(f"Error : {e}")


    # =========================
    # PAYMENT ENTRY TAB
    # =========================
    with tab3:
        st.subheader("Add Payment")

        payment_filter = ""
        if st.session_state.role != "Super Admin":
            payment_filter = f"AND branch_id = {st.session_state.branch_id}"

        sale_dropdown_df = pd.read_sql(
            f"""
            SELECT sale_id, name, pending_amount
            FROM customer_sales
            WHERE status='Open' {payment_filter}
            ORDER BY sale_id
            """,
            conn
        )

        if len(sale_dropdown_df) > 0:
            sale_options = []
            for _, row in sale_dropdown_df.iterrows():
                sale_options.append(f"{row['sale_id']} - {row['name']} (Pending ₹{row['pending_amount']:,.0f})")

            selected_sale = st.selectbox("Select Sale", sale_options)
            payment_date = st.date_input("Payment Date", value=date.today(), key="payment_date")
            amount_paid = st.number_input("Amount Paid", min_value=0.0, value=0.0, step=100.0, key="amount_paid")
            payment_method = st.selectbox("Payment Method", ["Cash", "Card", "UPI"], key="payment_method")

            if st.button("Add Payment"):
                try:
                    sale_id = int(selected_sale.split("-")[0].strip())
                    cursor = conn.cursor()

                    insert_payment_query = """
                    INSERT INTO payment_splits (sale_id, payment_date, amount_paid, payment_method)
                    VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(insert_payment_query, (sale_id, payment_date, amount_paid, payment_method))
                    conn.commit()

                    update_received_query = """
                    UPDATE customer_sales cs
                    SET received_amount = (
                        SELECT IFNULL(SUM(amount_paid), 0)
                        FROM payment_splits ps
                        WHERE ps.sale_id = cs.sale_id
                    )
                    WHERE cs.sale_id=%s
                    """
                    cursor.execute(update_received_query, (sale_id,))
                    conn.commit()

                    update_status_query = """
                    UPDATE customer_sales
                    SET status = CASE WHEN pending_amount <= 0 THEN 'Close' ELSE 'Open' END
                    WHERE sale_id=%s
                    """
                    cursor.execute(update_status_query, (sale_id,))
                    conn.commit()

                    st.success("Payment Added Successfully!")
                except Exception as e:
                    st.error(f"Error : {e}")
        else:
            st.info("No Open Sales Available")


    # =========================
    # QUERIES TAB
    # =========================
    with tab4:
        st.subheader("Business Insights & Database Queries")
        st.info("Explore business insights and database analytics using pre-built SQL queries.")

        # Updated analysis dropdown options
        query_option = st.selectbox(
            "Select Query",
            [
                "View Customer Sales Data",
                "View Branch Information",
                "View Payment Records",
                "View Open Sales",
                "Calculate Total Gross Sales",
                "Calculate Total Received Amount",
                "Calculate Total Pending Amount",
                "Count Sales by Branch",
                "Sales Details with Branch Name",
                "Sales Details with Payment Summary",
                "Branch-wise Gross Sales Analysis",
                "Sales with Payment Method Details",
                "Customers with Pending Amount > ₹5,000",
                "Top 3 Highest Gross Sales",
                "Branch with Highest Gross Sales"
            ]
        )

        is_admin = st.session_state.role != "Super Admin"
        admin_bid = st.session_state.branch_id

        # Updated IF/ELIF conditional logic statements
        if query_option == "View Customer Sales Data":
            sql = "SELECT * FROM customer_sales" if not is_admin else f"SELECT * FROM customer_sales WHERE branch_id = {admin_bid}"

        elif query_option == "View Branch Information":
            sql = "SELECT * FROM branches" if not is_admin else f"SELECT * FROM branches WHERE branch_id = {admin_bid}"

        elif query_option == "View Payment Records":
            if not is_admin:
                sql = "SELECT * FROM payment_splits"
            else:
                sql = f"""
                SELECT ps.* FROM payment_splits ps 
                JOIN customer_sales cs ON ps.sale_id = cs.sale_id 
                WHERE cs.branch_id = {admin_bid}
                """

        elif query_option == "View Open Sales":
            sql = "SELECT * FROM customer_sales WHERE status='Open'" if not is_admin else f"SELECT * FROM customer_sales WHERE status='Open' AND branch_id = {admin_bid}"

        elif query_option == "Calculate Total Gross Sales":
            sql = "SELECT SUM(gross_sales) AS Total_Revenue FROM customer_sales" if not is_admin else f"SELECT SUM(gross_sales) AS Total_Revenue FROM customer_sales WHERE branch_id = {admin_bid}"

        elif query_option == "Calculate Total Received Amount":
            sql = "SELECT SUM(received_amount) AS Total_Received FROM customer_sales" if not is_admin else f"SELECT SUM(received_amount) AS Total_Received FROM customer_sales WHERE branch_id = {admin_bid}"

        elif query_option == "Calculate Total Pending Amount":
            sql = "SELECT SUM(pending_amount) AS Total_Outstanding FROM customer_sales" if not is_admin else f"SELECT SUM(pending_amount) AS Total_Outstanding FROM customer_sales WHERE branch_id = {admin_bid}"

        elif query_option == "Count Sales by Branch":
            join_clause = "" if not is_admin else f"WHERE cs.branch_id = {admin_bid}"
            sql = f"""
            SELECT b.branch_name, COUNT(cs.sale_id) AS Sales_Count
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            {join_clause}
            GROUP BY b.branch_name
            ORDER BY Sales_Count DESC
            """

        elif query_option == "Sales Details with Branch Name":
            join_clause = "" if not is_admin else f"WHERE cs.branch_id = {admin_bid}"
            sql = f"""
            SELECT cs.sale_id, cs.name, cs.product_name, cs.gross_sales, b.branch_name
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            {join_clause}
            """

        elif query_option == "Sales Details with Payment Summary":
            join_clause = "" if not is_admin else f"WHERE cs.branch_id = {admin_bid}"
            sql = f"""
            SELECT cs.sale_id, cs.name, cs.gross_sales, SUM(ps.amount_paid) AS Total_Payment_Received
            FROM customer_sales cs
            JOIN payment_splits ps ON cs.sale_id = ps.sale_id
            {join_clause}
            GROUP BY cs.sale_id, cs.name, cs.gross_sales
            """

        elif query_option == "Branch-wise Gross Sales Analysis":
            join_clause = "" if not is_admin else f"WHERE cs.branch_id = {admin_bid}"
            sql = f"""
            SELECT b.branch_name, SUM(cs.gross_sales) AS Total_Revenue
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            {join_clause}
            GROUP BY b.branch_name
            ORDER BY Total_Revenue DESC
            """

        elif query_option == "Sales with Payment Method Details":
            join_clause = "" if not is_admin else f"WHERE cs.branch_id = {admin_bid}"
            sql = f"""
            SELECT cs.sale_id, cs.name, ps.payment_method, ps.amount_paid
            FROM customer_sales cs
            JOIN payment_splits ps ON cs.sale_id = ps.sale_id
            {join_clause}
            """

        elif query_option == "Customers with Pending Amount > ₹5,000":
            admin_clause = "" if not is_admin else f"AND branch_id = {admin_bid}"
            sql = f"""
            SELECT sale_id, name, pending_amount
            FROM customer_sales
            WHERE pending_amount > 5000 {admin_clause}
            ORDER BY pending_amount DESC
            """

        elif query_option == "Top 3 Highest Gross Sales":
            admin_clause = "" if not is_admin else f"WHERE branch_id = {admin_bid}"
            sql = f"""
            SELECT sale_id, name, gross_sales
            FROM customer_sales
            {admin_clause}
            ORDER BY gross_sales DESC
            LIMIT 3
            """

        elif query_option == "Branch with Highest Gross Sales":
            join_clause = "" if not is_admin else f"WHERE cs.branch_id = {admin_bid}"
            sql = f"""
            SELECT b.branch_name, SUM(cs.gross_sales) AS Total_Revenue
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            {join_clause}
            GROUP BY b.branch_name
            ORDER BY Total_Revenue DESC
            LIMIT 1
            """

        result_df = pd.read_sql(sql, conn)
        st.dataframe(result_df, use_container_width=True)

    # =========================
    # CLOSE CONNECTION
    # =========================
    conn.close()