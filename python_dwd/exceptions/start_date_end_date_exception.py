""" Exception that can thrown if Start and Date are not aligned """


class StartDateEndDateError(Exception):
    print("Error: 'start_date' must be smaller or equal to 'end_date'.")
