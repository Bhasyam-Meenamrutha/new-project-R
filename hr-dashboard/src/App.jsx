import { useEffect, useMemo, useRef, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [employees, setEmployees] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [cameraStatus, setCameraStatus] = useState(null);

  const [loading, setLoading] = useState(true);
  const [cameraLoading, setCameraLoading] = useState(true);
  const [error, setError] = useState("");
  const [cameraError, setCameraError] = useState("");

  const [activePage, setActivePage] = useState("dashboard");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Date used by the Attendance page.
  // Dashboard continues to use today's live attendance.
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [dateAttendanceLoading, setDateAttendanceLoading] = useState(false);
  const [dateAttendanceError, setDateAttendanceError] = useState("");

  // Employee attendance calendar state.
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [attendanceHistory, setAttendanceHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyYear, setHistoryYear] = useState(new Date().getFullYear());
  const [historyMonth, setHistoryMonth] = useState(new Date().getMonth() + 1);
  const [selectedHistoryDay, setSelectedHistoryDay] = useState(null);

  // Excel report download chooser.
  const [reportChooser, setReportChooser] = useState(null);
  const [reportDownloading, setReportDownloading] = useState(false);
  const [reportError, setReportError] = useState("");

  const [showAddEmployee, setShowAddEmployee] = useState(false);
  const [employeeForm, setEmployeeForm] = useState({
    login_id: "",
    shift_start: "14:00",
    shift_end: "22:00",
  });

  const [formMessage, setFormMessage] = useState("");
  const [formError, setFormError] = useState("");

  // Edit an employee's shift timing. Changes are saved by the FastAPI backend.
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [editShiftForm, setEditShiftForm] = useState({
    shift_start: "",
    shift_end: "",
  });
  const [editShiftLoading, setEditShiftLoading] = useState(false);
  const [editShiftError, setEditShiftError] = useState("");

  // Face enrollment / camera capture state.
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [cameraStream, setCameraStream] = useState(null);
  const [captureError, setCaptureError] = useState("");
  const [capturedPhotos, setCapturedPhotos] = useState([]);
  const [enrollmentLoading, setEnrollmentLoading] = useState(false);

  const openEditShift = (employee) => {
    setEditingEmployee(employee);
    setEditShiftForm({
      shift_start: employee.shift_start || "09:00",
      shift_end: employee.shift_end || "17:00",
    });
    setEditShiftError("");
  };

  const saveEmployeeShift = async (event) => {
    event.preventDefault();
    if (!editingEmployee) return;

    if (!editShiftForm.shift_start || !editShiftForm.shift_end) {
      setEditShiftError("Please enter both shift start and shift end.");
      return;
    }

    setEditShiftLoading(true);
    setEditShiftError("");
    try {
      const response = await fetch(
        `${API_URL}/employees/${encodeURIComponent(editingEmployee.employee_id)}/shift`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(editShiftForm),
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to update employee shift.");
      }

      // Update the visible card immediately, then refresh backend data.
      setEmployees((previous) => previous.map((employee) =>
        employee.employee_id === data.employee.employee_id
          ? { ...employee, ...data.employee }
          : employee
      ));
      await loadDashboardData();
      setEditingEmployee(null);
    } catch (err) {
      setEditShiftError(err.message || "Unable to update employee shift.");
    } finally {
      setEditShiftLoading(false);
    }
  };

  const loadDashboardData = async () => {
    try {
      setError("");

      const [employeesResponse, attendanceResponse] = await Promise.all([
        fetch(`${API_URL}/employees`),
        fetch(`${API_URL}/attendance/today`),
      ]);

      if (!employeesResponse.ok) {
        throw new Error("Unable to load employees");
      }

      if (!attendanceResponse.ok) {
        throw new Error("Unable to load attendance");
      }

      const employeesData = await employeesResponse.json();
      const attendanceData = await attendanceResponse.json();

      setEmployees(Array.isArray(employeesData) ? employeesData : []);

      const attendanceList = Array.isArray(attendanceData)
        ? attendanceData
        : attendanceData?.attendance || attendanceData?.data || [];

      setAttendance(attendanceList);
    } catch (err) {
      setError(err.message || "Unable to connect to backend");
    } finally {
      setLoading(false);
    }
  };

  const loadAttendanceByDate = async (date) => {
    if (!date) return;

    try {
      setDateAttendanceLoading(true);
      setDateAttendanceError("");

      const response = await fetch(
        `${API_URL}/attendance/date/${date}`
      );

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          data.detail || "Unable to load attendance for selected date"
        );
      }

      const data = await response.json();

      const attendanceList = Array.isArray(data)
        ? data
        : data?.attendance || data?.data || [];

      setAttendance(attendanceList);
    } catch (err) {
      setDateAttendanceError(
        err.message || "Unable to load selected date"
      );
      setAttendance([]);
    } finally {
      setDateAttendanceLoading(false);
    }
  };

  const loadCameraStatus = async () => {
    try {
      setCameraError("");

      const response = await fetch(`${API_URL}/cameras/status`);

      if (!response.ok) {
        throw new Error("Unable to load camera status");
      }

      const data = await response.json();
      setCameraStatus(data);
    } catch (err) {
      setCameraError(err.message || "Unable to load camera status");
    } finally {
      setCameraLoading(false);
    }
  };

  const handleAttendanceDateChange = (event) => {
    const date = event.target.value;

    setSelectedDate(date);

    if (date) {
      loadAttendanceByDate(date);
    }
  };

  useEffect(() => {
    if (activePage === "attendance") {
      loadAttendanceByDate(selectedDate);
    } else {
      loadDashboardData();
    }

    loadCameraStatus();

    const interval = setInterval(() => {
      loadCameraStatus();

      if (activePage === "dashboard") {
        loadDashboardData();
      } else if (activePage === "attendance") {
        loadAttendanceByDate(selectedDate);
      } else if (activePage === "employees") {
        loadDashboardData();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [activePage, selectedDate]);

  const handleEmployeeFormChange = (event) => {
    const { name, value } = event.target;

    setEmployeeForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const startEnrollmentCamera = async () => {
    setCaptureError("");

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          "Camera access is not supported by this browser."
        );
      }

      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "user",
        },
        audio: false,
      });

      setCameraStream(stream);

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      setCaptureError(
        err.message ||
          "Unable to access the camera. Please allow camera permission."
      );
    }
  };

  const stopEnrollmentCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
    }

    setCameraStream(null);

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  useEffect(() => {
    if (cameraStream && videoRef.current) {
      videoRef.current.srcObject = cameraStream;
      videoRef.current.play().catch(() => {});
    }
  }, [cameraStream]);


  useEffect(() => {
    return () => {
      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [cameraStream]);

  const resetEnrollmentState = () => {
    stopEnrollmentCamera();

    capturedPhotos.forEach((photo) => {
      if (photo.previewUrl) {
        URL.revokeObjectURL(photo.previewUrl);
      }
    });

    setCapturedPhotos([]);
    setCaptureError("");
    setEnrollmentLoading(false);
  };

  const closeAddEmployee = () => {
    resetEnrollmentState();
    setShowAddEmployee(false);
    setFormMessage("");
    setFormError("");
  };

  const captureSnapshot = () => {
    setCaptureError("");

    if (!videoRef.current || !canvasRef.current) {
      setCaptureError("Camera is not ready yet.");
      return;
    }

    const video = videoRef.current;

    if (video.readyState < 2) {
      setCaptureError("Please wait for the camera preview to become ready.");
      return;
    }

    if (capturedPhotos.length >= 10) {
      setCaptureError("Maximum 10 photos can be captured.");
      return;
    }

    const canvas = canvasRef.current;
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;

    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");

    if (!context) {
      setCaptureError("Unable to capture the camera frame.");
      return;
    }

    context.drawImage(video, 0, 0, width, height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setCaptureError("Unable to create snapshot.");
          return;
        }

        const previewUrl = URL.createObjectURL(blob);

        setCapturedPhotos((previous) => [
          ...previous,
          {
            blob,
            previewUrl,
            filename: `face_${previous.length + 1}.jpg`,
          },
        ]);
      },
      "image/jpeg",
      0.92
    );
  };

  const removeCapturedPhoto = (index) => {
    setCapturedPhotos((previous) => {
      const photo = previous[index];

      if (photo?.previewUrl) {
        URL.revokeObjectURL(photo.previewUrl);
      }

      return previous.filter((_, photoIndex) => photoIndex !== index);
    });
  };

  const addEmployee = async (event) => {
    event.preventDefault();

    setFormMessage("");
    setFormError("");
    setCaptureError("");

    if (capturedPhotos.length < 5) {
      setCaptureError(
        "Please capture at least 5 face photos before adding the employee."
      );
      return;
    }

    if (capturedPhotos.length > 10) {
      setCaptureError("You can capture a maximum of 10 photos.");
      return;
    }

    setEnrollmentLoading(true);

    let employeeCreated = false;

    try {
      // ----------------------------------------------------
      // STEP 1: CREATE EMPLOYEE
      // ----------------------------------------------------

      const employeeResponse = await fetch(`${API_URL}/employees`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(employeeForm),
      });

      const employeeData = await employeeResponse.json();

      if (!employeeResponse.ok) {
        throw new Error(
          employeeData.detail || "Unable to add employee"
        );
      }

      employeeCreated = true;

      // ----------------------------------------------------
      // STEP 2: SEND CAPTURED PHOTOS FOR FACE ENROLLMENT
      // ----------------------------------------------------

      const formData = new FormData();

      capturedPhotos.forEach((photo, index) => {
        formData.append(
          "files",
          photo.blob,
          photo.filename || `face_${index + 1}.jpg`
        );
      });

      const enrollmentResponse = await fetch(
        `${API_URL}/employees/${encodeURIComponent(
          employeeForm.login_id
        )}/enroll-face`,
        {
          method: "POST",
          body: formData,
        }
      );

      const enrollmentData = await enrollmentResponse.json();

      if (!enrollmentResponse.ok) {
        const detail =
          typeof enrollmentData.detail === "string"
            ? enrollmentData.detail
            : enrollmentData.detail?.message ||
              "Face enrollment failed.";

        throw new Error(detail);
      }

      setFormMessage(
        `Employee added and face enrolled successfully. ${enrollmentData.photos_processed || capturedPhotos.length} photos processed.`
      );

      // ----------------------------------------------------
      // CLEANUP
      // ----------------------------------------------------

      resetEnrollmentState();

      setEmployeeForm({
        login_id: "",
        shift_start: "14:00",
        shift_end: "22:00",
      });

      await loadDashboardData();

      setTimeout(() => {
        setShowAddEmployee(false);
        setFormMessage("");
      }, 1500);
    } catch (err) {
      if (employeeCreated) {
        setFormError(
          `Employee was created, but face enrollment failed: ${
            err.message || "Unknown enrollment error"
          }`
        );
      } else {
        setFormError(err.message || "Unable to add employee");
      }
    } finally {
      setEnrollmentLoading(false);
    }
  };


  const loadEmployeeAttendanceHistory = async (
    employee,
    year,
    month
  ) => {
    if (!employee) return;

    setHistoryLoading(true);
    setHistoryError("");
    setSelectedHistoryDay(null);

    try {
      const response = await fetch(
        `${API_URL}/employees/${encodeURIComponent(
          employee.employee_id
        )}/attendance-history?year=${year}&month=${month}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to load attendance history"
        );
      }

      // The API returns `attendance` as an array. Keep a fallback for
      // older backend responses that returned { attendance: { attendance: [] } }.
      const history =
        Array.isArray(data?.attendance)
          ? data.attendance
          : Array.isArray(data?.attendance?.attendance)
          ? data.attendance.attendance
          : Array.isArray(data)
          ? data
          : [];

      setAttendanceHistory(history);
    } catch (err) {
      setAttendanceHistory([]);
      setHistoryError(
        err.message || "Unable to load attendance history"
      );
    } finally {
      setHistoryLoading(false);
    }
  };

  const openEmployeeHistory = async (employee) => {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;

    setSelectedEmployee(employee);
    setHistoryYear(year);
    setHistoryMonth(month);

    await loadEmployeeAttendanceHistory(employee, year, month);
  };

  const closeHistory = () => {
    setSelectedEmployee(null);
    setAttendanceHistory([]);
    setHistoryError("");
    setSelectedHistoryDay(null);
  };

  const openEmployeeReportChooser = () => {
    if (!selectedEmployee) return;

    const fallbackDate = `${historyYear}-${String(historyMonth).padStart(2, "0")}-01`;

    setReportError("");
    setReportChooser({
      type: "employee",
      employee: selectedEmployee,
      date: selectedHistoryDay?.date || fallbackDate,
    });
  };

  const openAllEmployeesReportChooser = () => {
    setReportError("");
    setReportChooser({
      type: "all",
      date: selectedDate,
    });
  };

  const closeReportChooser = () => {
    if (reportDownloading) return;
    setReportChooser(null);
    setReportError("");
  };

  const downloadAttendanceReport = async (period) => {
    if (!reportChooser) return;

    setReportDownloading(true);
    setReportError("");

    try {
      const date = reportChooser.date || new Date().toISOString().split("T")[0];
      const query = `period=${encodeURIComponent(period)}&date=${encodeURIComponent(date)}`;

      const url =
        reportChooser.type === "employee"
          ? `${API_URL}/reports/employee/${encodeURIComponent(reportChooser.employee.employee_id)}?${query}`
          : `${API_URL}/reports/attendance?${query}`;

      const response = await fetch(url);

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to download attendance report");
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const contentDisposition = response.headers.get("Content-Disposition") || "";
      const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
      const filename =
        filenameMatch?.[1] ||
        `${reportChooser.type === "employee" ? "employee" : "all_employees"}_attendance_${period}.xlsx`;

      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(objectUrl);

      setReportChooser(null);
    } catch (err) {
      setReportError(err.message || "Unable to download attendance report");
    } finally {
      setReportDownloading(false);
    }
  };

  const changeHistoryMonth = async (offset) => {
    if (!selectedEmployee) return;

    let nextMonth = historyMonth + offset;
    let nextYear = historyYear;

    if (nextMonth < 1) {
      nextMonth = 12;
      nextYear -= 1;
    } else if (nextMonth > 12) {
      nextMonth = 1;
      nextYear += 1;
    }

    setHistoryYear(nextYear);
    setHistoryMonth(nextMonth);

    await loadEmployeeAttendanceHistory(
      selectedEmployee,
      nextYear,
      nextMonth
    );
  };

  const getHistoryStatusMeta = (status) => {
    const normalized = String(status || "ABSENT").toUpperCase();

    const values = {
      FULL_DAY: {
        label: "Full Day",
        className: "history-full-day",
      },
      HALF_DAY: {
        label: "Half Day",
        className: "history-half-day",
      },
      LEAVE: {
        label: "Leave",
        className: "history-leave",
      },
      ABSENT: {
        label: "Absent",
        className: "history-absent",
      },
      WEEKEND: {
        label: "Weekend",
        className: "history-weekend",
      },
    };

    return values[normalized] || values.ABSENT;
  };

  const getHistoryCalendarCells = () => {
    const firstDay = new Date(
      historyYear,
      historyMonth - 1,
      1
    ).getDay();

    return [
      ...Array(firstDay).fill(null),
      ...attendanceHistory,
    ];
  };

  const historyMonthTitle = new Date(
    historyYear,
    historyMonth - 1,
    1
  ).toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });

  const getAttendance = (employeeId) => {
    return attendance.find(
      (record) => String(record.employee_id) === String(employeeId)
    );
  };

  const getStatus = (record) => {
    if (!record || Number(record.event_count || 0) === 0) {
      return "ABSENT";
    }

    const workedMinutes = Number(record.worked_minutes || 0);

    if (workedMinutes < 240) return "ABSENT";
    if (workedMinutes < 480) return "HALF_DAY";

    return "FULL_DAY";
  };

  const formatStatus = (status) => {
    if (status === "ON_TIME") return "ON TIME";
    if (status === "HALF_DAY") return "HALF DAY";
    if (status === "FULL_DAY") return "FULL DAY";
    if (status === "ABSENT") return "ABSENT";
    return status;
  };

  const filteredEmployees = useMemo(() => {
    return employees.filter((employee) => {
      const employeeAttendance = getAttendance(employee.employee_id);
      const status = getStatus(employeeAttendance);

      const query = search.toLowerCase().trim();

      const matchesSearch =
        !query ||
        String(employee.employee_id).toLowerCase().includes(query) ||
        String(employee.employee_name || "")
          .toLowerCase()
          .includes(query);

      let matchesFilter = true;

      if (statusFilter === "ALL") {
        matchesFilter = true;
      } else if (statusFilter === "ABSENT") {
        matchesFilter = status === "ABSENT";
      } else if (statusFilter === "HALF_DAY") {
        matchesFilter = status === "HALF_DAY";
      } else if (statusFilter === "FULL_DAY") {
        matchesFilter = status === "FULL_DAY";
      } else if (statusFilter === "INSIDE") {
        matchesFilter =
          String(employeeAttendance?.current_state || "").toUpperCase() ===
          "INSIDE";
      } else if (statusFilter === "OUTSIDE") {
        matchesFilter =
          String(employeeAttendance?.current_state || "").toUpperCase() ===
          "OUTSIDE";
      }

      return matchesSearch && matchesFilter;
    });
  }, [employees, attendance, search, statusFilter]);

  const totalEmployees = employees.length;

  const presentToday = attendance.filter(
    (record) => getStatus(record) !== "ABSENT"
  ).length;

  const lateToday = attendance.filter(
    (record) => String(record.arrival_status || "").toUpperCase() === "LATE"
  ).length;

  const insideNow = attendance.filter(
    (record) =>
      String(record.current_state || "").toUpperCase() === "INSIDE"
  ).length;

  const getCamera = (type) => {
    if (!cameraStatus) return null;

    if (type === "ENTRY") {
      return cameraStatus.entry_camera || cameraStatus.entry || null;
    }

    return cameraStatus.exit_camera || cameraStatus.exit || null;
  };

  const entryCamera = getCamera("ENTRY");
  const exitCamera = getCamera("EXIT");

  const isCameraConnected = (camera) => {
    return Boolean(camera?.connected || camera?.device_exists);
  };

  const formatMinutes = (minutes) => {
    const value = Number(minutes || 0);

    const hours = Math.floor(value / 60);
    const mins = value % 60;

    if (hours === 0) return `${mins}m`;

    return `${hours}h ${mins}m`;
  };

  const formatWorkedTime = (record) => {
    if (record?.worked_hours) {
      return record.worked_hours;
    }

    return formatMinutes(record?.worked_minutes);
  };

  const formatTime = (time) => {
    if (!time) return "--";

    const parts = String(time).split(":");

    if (parts.length < 2) return time;

    let hour = Number(parts[0]);
    const minute = parts[1];

    const suffix = hour >= 12 ? "PM" : "AM";

    hour = hour % 12 || 12;

    return `${hour}:${minute} ${suffix}`;
  };

  const todayText = new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });

  const selectedDateText = selectedDate
    ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString("en-IN", {
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    : "";

  const statusClass = (status) => {
    switch (status) {
      case "EARLY":
        return "status-early";

      case "LATE":
        return "status-late";

      case "ON_TIME":
        return "status-ontime";

      case "INSIDE":
        return "status-inside";

      case "OUTSIDE":
        return "status-outside";

      case "ABSENT":
        return "status-absent";

      case "HALF_DAY":
        return "status-half-day";

      case "FULL_DAY":
        return "status-full-day";

      default:
        return "status-neutral";
    }
  };

  return (
    <div className="app-shell">
      <style>{`
        * {
          box-sizing: border-box;
        }

        body {
          margin: 0;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system,
            BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f5f7fb;
          color: #172033;
        }

        button,
        input,
        select {
          font: inherit;
        }

        button {
          cursor: pointer;
        }

        .app-shell {
          min-height: 100vh;
          display: flex;
          background: #f5f7fb;
        }

        .sidebar {
          width: 245px;
          min-height: 100vh;
          background: #101828;
          color: white;
          padding: 24px 16px;
          position: fixed;
          left: 0;
          top: 0;
          bottom: 0;
          z-index: 20;
        }

        .brand {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 0 10px 28px;
          border-bottom: 1px solid rgba(255,255,255,.08);
        }

        .brand-icon {
          width: 42px;
          height: 42px;
          border-radius: 12px;
          background: linear-gradient(135deg, #4f46e5, #7c3aed);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          font-weight: 800;
        }

        .brand-title {
          font-size: 18px;
          font-weight: 750;
          letter-spacing: -.3px;
        }

        .brand-subtitle {
          font-size: 11px;
          color: #98a2b3;
          margin-top: 2px;
        }

        .nav-title {
          color: #667085;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 1px;
          margin: 28px 10px 10px;
          text-transform: uppercase;
        }

        .nav-item {
          width: 100%;
          border: 0;
          background: transparent;
          color: #98a2b3;
          padding: 12px 13px;
          border-radius: 9px;
          display: flex;
          align-items: center;
          gap: 12px;
          text-align: left;
          margin-bottom: 4px;
          transition: .2s ease;
        }

        .nav-item:hover {
          background: rgba(255,255,255,.05);
          color: white;
        }

        .nav-item.active {
          background: #344054;
          color: white;
        }

        .nav-icon {
          width: 20px;
          text-align: center;
          font-size: 15px;
        }

        .sidebar-footer {
          position: absolute;
          left: 16px;
          right: 16px;
          bottom: 20px;
          border-top: 1px solid rgba(255,255,255,.08);
          padding: 18px 10px 0;
          color: #667085;
          font-size: 11px;
          line-height: 1.6;
        }

        .main {
          width: calc(100% - 245px);
          margin-left: 245px;
          min-height: 100vh;
        }

        .topbar {
          height: 72px;
          background: white;
          border-bottom: 1px solid #eaecf0;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 32px;
          position: sticky;
          top: 0;
          z-index: 10;
        }

        .breadcrumb {
          color: #667085;
          font-size: 13px;
        }

        .topbar-right {
          display: flex;
          align-items: center;
          gap: 18px;
        }

        .system-status {
          display: flex;
          align-items: center;
          gap: 7px;
          color: #344054;
          font-size: 13px;
          font-weight: 600;
        }

        .online-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #12b76a;
          box-shadow: 0 0 0 3px #dcfae6;
        }

        .refresh-button {
          border: 1px solid #d0d5dd;
          background: white;
          color: #344054;
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 600;
        }

        .refresh-button:hover {
          background: #f9fafb;
        }

        .content {
          padding: 32px;
          max-width: 1700px;
          margin: auto;
        }

        .page-heading {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 28px;
        }

        .page-title {
          margin: 0;
          font-size: 27px;
          letter-spacing: -.6px;
          color: #101828;
        }

        .page-description {
          margin: 7px 0 0;
          color: #667085;
          font-size: 13px;
        }

        .primary-button {
          border: 0;
          background: #4f46e5;
          color: white;
          border-radius: 8px;
          padding: 11px 16px;
          font-weight: 650;
          font-size: 13px;
          box-shadow: 0 2px 5px rgba(79,70,229,.2);
        }

        .primary-button:hover {
          background: #4338ca;
        }

        .primary-button:disabled {
          opacity: .6;
          cursor: not-allowed;
        }

        .report-download-button {
          white-space: nowrap;
        }

        .report-chooser-backdrop {
          z-index: 120;
        }

        .report-chooser-modal {
          background: white;
          width: min(560px, 100%);
          border-radius: 14px;
          box-shadow: 0 20px 60px rgba(16,24,40,.24);
        }

        .report-chooser-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .report-option {
          border: 1px solid #d0d5dd;
          background: white;
          border-radius: 10px;
          padding: 16px;
          display: flex;
          align-items: flex-start;
          gap: 12px;
          text-align: left;
          color: #344054;
          transition: .15s ease;
        }

        .report-option:hover:not(:disabled) {
          border-color: #a5b4fc;
          background: #f9faff;
          transform: translateY(-1px);
        }

        .report-option:disabled {
          opacity: .6;
          cursor: not-allowed;
        }

        .report-option span:last-child {
          display: grid;
          gap: 5px;
        }

        .report-option strong {
          color: #101828;
          font-size: 13px;
        }

        .report-option small {
          color: #667085;
          font-size: 10px;
          line-height: 1.45;
        }

        .report-option-icon {
          width: 34px;
          height: 34px;
          border-radius: 8px;
          background: #eef2ff;
          color: #4338ca;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 800;
          flex: 0 0 auto;
        }

        .report-download-status {
          margin-top: 12px;
          padding: 10px 12px;
          border-radius: 8px;
          background: #f9fafb;
          color: #667085;
          font-size: 11px;
          text-align: center;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
          margin-bottom: 24px;
        }

        .stat-card {
          background: white;
          border: 1px solid #eaecf0;
          border-radius: 12px;
          padding: 20px;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }

        .stat-label {
          color: #667085;
          font-size: 12px;
          font-weight: 600;
        }

        .stat-value {
          font-size: 27px;
          font-weight: 750;
          color: #101828;
          margin-top: 8px;
        }

        .stat-icon {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: #eef2ff;
          color: #4f46e5;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
        }

        .section {
          margin-bottom: 24px;
        }

        .section-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 13px;
        }

        .section-title {
          font-size: 15px;
          font-weight: 700;
          color: #101828;
        }

        .section-caption {
          color: #667085;
          font-size: 12px;
        }

        .camera-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 16px;
        }

        .camera-card {
          background: white;
          border: 1px solid #eaecf0;
          border-radius: 12px;
          padding: 20px;
        }

        .camera-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }

        .camera-name {
          font-size: 14px;
          font-weight: 750;
          color: #101828;
        }

        .camera-responsibility {
          color: #667085;
          font-size: 12px;
          margin-top: 5px;
        }

        .connection-badge {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 5px 9px;
          border-radius: 999px;
          font-size: 10px;
          font-weight: 700;
        }

        .connection-badge.connected {
          color: #067647;
          background: #ecfdf3;
        }

        .connection-badge.disconnected {
          color: #b42318;
          background: #fef3f2;
        }

        .camera-details {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-top: 20px;
          padding-top: 16px;
          border-top: 1px solid #f2f4f7;
        }

        .detail-label {
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: .5px;
          color: #98a2b3;
          font-weight: 700;
        }

        .detail-value {
          font-size: 12px;
          color: #344054;
          font-weight: 600;
          margin-top: 4px;
        }

        .table-card {
          background: white;
          border: 1px solid #eaecf0;
          border-radius: 12px;
          overflow: hidden;
        }

        .table-toolbar {
          padding: 16px;
          border-bottom: 1px solid #eaecf0;
          display: flex;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
        }

        .search-box {
          min-width: 260px;
          position: relative;
        }

        .search-box input {
          width: 100%;
          border: 1px solid #d0d5dd;
          border-radius: 8px;
          padding: 9px 12px 9px 34px;
          outline: none;
          font-size: 12px;
        }

        .search-box input:focus {
          border-color: #7f56d9;
          box-shadow: 0 0 0 3px #f4f3ff;
        }

        .search-icon {
          position: absolute;
          left: 12px;
          top: 8px;
          color: #98a2b3;
        }

        .filter-group {
          display: flex;
          gap: 5px;
          flex-wrap: wrap;
        }

        .filter-button {
          border: 1px solid #eaecf0;
          background: white;
          color: #667085;
          border-radius: 7px;
          padding: 7px 10px;
          font-size: 11px;
          font-weight: 600;
        }

        .filter-button.active {
          background: #eef2ff;
          color: #4338ca;
          border-color: #c7d2fe;
        }

        .table-wrapper {
          overflow-x: auto;
        }

        table {
          width: 100%;
          border-collapse: collapse;
          min-width: 850px;
        }

        th {
          background: #f9fafb;
          color: #667085;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: .5px;
          text-align: left;
          padding: 12px 16px;
          font-weight: 700;
          border-bottom: 1px solid #eaecf0;
        }

        td {
          padding: 14px 16px;
          border-bottom: 1px solid #f2f4f7;
          color: #344054;
          font-size: 12px;
        }

        tr:last-child td {
          border-bottom: 0;
        }

        .employee-cell {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .avatar {
          width: 34px;
          height: 34px;
          border-radius: 9px;
          background: #eef2ff;
          color: #4338ca;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 750;
          font-size: 12px;
        }

        .employee-name {
          font-weight: 700;
          color: #101828;
        }

        .employee-id {
          color: #98a2b3;
          font-size: 10px;
          margin-top: 2px;
        }

        .status-badge {
          display: inline-flex;
          align-items: center;
          padding: 4px 8px;
          border-radius: 999px;
          font-size: 9px;
          font-weight: 750;
          letter-spacing: .2px;
        }

        .status-early {
          background: #ecfdf3;
          color: #067647;
        }

        .status-late {
          background: #fef3f2;
          color: #b42318;
        }

        .status-ontime {
          background: #eff8ff;
          color: #175cd3;
        }

        .status-inside {
          background: #f4f3ff;
          color: #6941c6;
        }

        .status-outside {
          background: #f2f4f7;
          color: #475467;
        }

        .status-absent {
          background: #fef3f2;
          color: #b42318;
        }

        .status-neutral {
          background: #f2f4f7;
          color: #475467;
        }

        .action-button {
          border: 0;
          background: transparent;
          color: #4f46e5;
          font-size: 11px;
          font-weight: 700;
        }

        .action-button:hover {
          text-decoration: underline;
        }

        .empty-state {
          text-align: center;
          padding: 50px 20px;
          color: #98a2b3;
        }

        .empty-icon {
          font-size: 30px;
          margin-bottom: 10px;
        }

        .message {
          padding: 12px 14px;
          border-radius: 8px;
          font-size: 12px;
          margin-bottom: 16px;
        }

        .error-message {
          background: #fef3f2;
          color: #b42318;
          border: 1px solid #fecdca;
        }

        .success-message {
          background: #ecfdf3;
          color: #067647;
          border: 1px solid #abefc6;
        }

        .page-panel {
          background: white;
          border: 1px solid #eaecf0;
          border-radius: 12px;
          padding: 22px;
        }

        .employee-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 14px;
        }

        .employee-card {
          border: 1px solid #eaecf0;
          border-radius: 10px;
          padding: 16px;
          background: white;
        }

        .employee-card-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .employee-card-name {
          font-size: 14px;
          font-weight: 700;
          color: #101828;
        }

        .employee-card-id {
          font-size: 11px;
          color: #98a2b3;
          margin-top: 3px;
        }

        .employee-info {
          margin-top: 16px;
          display: grid;
          gap: 8px;
        }

        .info-row {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
        }

        .info-row span:first-child {
          color: #98a2b3;
        }

        .info-row span:last-child {
          color: #344054;
          font-weight: 600;
        }

        .modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(16,24,40,.55);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          z-index: 100;
        }

        .modal {
          background: white;
          width: min(700px, 100%);
          max-height: 85vh;
          overflow-y: auto;
          border-radius: 14px;
          box-shadow: 0 20px 60px rgba(16,24,40,.2);
        }

        .modal-header {
          padding: 20px;
          border-bottom: 1px solid #eaecf0;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }

        .modal-title {
          margin: 0;
          font-size: 17px;
          color: #101828;
        }

        .modal-subtitle {
          margin-top: 4px;
          color: #667085;
          font-size: 11px;
        }

        .close-button {
          border: 0;
          background: #f2f4f7;
          width: 30px;
          height: 30px;
          border-radius: 7px;
          color: #667085;
        }

        .modal-body {
          padding: 20px;
        }

        .event-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 0;
          border-bottom: 1px solid #f2f4f7;
        }

        .event-row:last-child {
          border-bottom: 0;
        }

        .event-date {
          font-size: 11px;
          color: #667085;
        }

        .event-time {
          font-size: 13px;
          font-weight: 700;
          color: #101828;
          margin-top: 3px;
        }

        .event-in {
          color: #067647;
          background: #ecfdf3;
        }

        .event-out {
          color: #b42318;
          background: #fef3f2;
        }

        .event-type {
          padding: 5px 9px;
          border-radius: 999px;
          font-size: 9px;
          font-weight: 750;
        }

        .form-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 14px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-group.full {
          grid-column: 1 / -1;
        }

        .form-group label {
          color: #344054;
          font-size: 11px;
          font-weight: 650;
        }

        .form-group input {
          border: 1px solid #d0d5dd;
          border-radius: 8px;
          padding: 10px;
          outline: none;
          font-size: 12px;
        }

        .form-group input:focus {
          border-color: #7f56d9;
          box-shadow: 0 0 0 3px #f4f3ff;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          padding: 16px 20px;
          border-top: 1px solid #eaecf0;
        }

        .secondary-button {
          border: 1px solid #d0d5dd;
          background: white;
          color: #344054;
          border-radius: 8px;
          padding: 10px 14px;
          font-size: 12px;
          font-weight: 650;
        }

        .enrollment-section {
          margin-top: 20px;
          padding-top: 20px;
          border-top: 1px solid #eaecf0;
        }

        .enrollment-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
          margin-bottom: 12px;
        }

        .enrollment-title {
          font-size: 13px;
          font-weight: 750;
          color: #101828;
        }

        .enrollment-caption {
          margin-top: 4px;
          color: #667085;
          font-size: 11px;
          line-height: 1.5;
        }

        .capture-layout {
          display: grid;
          grid-template-columns: 1.35fr .65fr;
          gap: 16px;
          align-items: start;
        }

        .camera-preview {
          width: 100%;
          aspect-ratio: 16 / 9;
          background: #101828;
          border-radius: 10px;
          overflow: hidden;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .camera-preview video {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          transform: scaleX(-1);
        }

        .camera-placeholder {
          color: #98a2b3;
          font-size: 12px;
          text-align: center;
          padding: 20px;
        }

        .capture-controls {
          display: flex;
          gap: 8px;
          margin-top: 10px;
          flex-wrap: wrap;
        }

        .capture-button {
          border: 0;
          background: #4f46e5;
          color: white;
          border-radius: 8px;
          padding: 9px 13px;
          font-size: 11px;
          font-weight: 700;
        }

        .capture-button:hover {
          background: #4338ca;
        }

        .capture-button:disabled {
          opacity: .5;
          cursor: not-allowed;
        }

        .camera-start-button {
          border: 1px solid #d0d5dd;
          background: white;
          color: #344054;
          border-radius: 8px;
          padding: 9px 13px;
          font-size: 11px;
          font-weight: 700;
        }

        .capture-count {
          margin-top: 9px;
          font-size: 11px;
          color: #667085;
          font-weight: 650;
        }

        .photo-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
        }

        .photo-card {
          position: relative;
          border: 1px solid #eaecf0;
          border-radius: 8px;
          overflow: hidden;
          background: #f9fafb;
        }

        .photo-card img {
          width: 100%;
          aspect-ratio: 1 / 1;
          object-fit: cover;
          display: block;
        }

        .remove-photo {
          position: absolute;
          right: 5px;
          top: 5px;
          width: 24px;
          height: 24px;
          border: 0;
          border-radius: 50%;
          background: rgba(16, 24, 40, .78);
          color: white;
          font-size: 14px;
          line-height: 24px;
          padding: 0;
        }

        .photo-number {
          position: absolute;
          left: 5px;
          bottom: 5px;
          background: rgba(16, 24, 40, .75);
          color: white;
          border-radius: 5px;
          padding: 3px 6px;
          font-size: 9px;
          font-weight: 700;
        }

        .capture-help {
          border: 1px solid #eaecf0;
          background: #f9fafb;
          border-radius: 9px;
          padding: 12px;
          color: #667085;
          font-size: 10px;
          line-height: 1.6;
        }

        .capture-help strong {
          color: #344054;
        }

        .history-modal-backdrop {
          align-items: center;
        }

        .history-modal {
          background: white;
          width: min(1100px, 100%);
          max-height: 94vh;
          overflow-y: auto;
          border-radius: 16px;
          box-shadow: 0 24px 70px rgba(16,24,40,.28);
        }

        .history-modal-header {
          padding: 20px 24px;
          border-bottom: 1px solid #eaecf0;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          position: sticky;
          top: 0;
          background: white;
          z-index: 2;
        }

        .history-modal-body {
          padding: 24px;
        }

        .history-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }

        .history-month-title {
          font-size: 19px;
          font-weight: 750;
          color: #101828;
        }

        .history-month-button {
          width: 40px;
          height: 40px;
          border: 1px solid #d0d5dd;
          background: white;
          border-radius: 9px;
          color: #344054;
          font-size: 18px;
          font-weight: 700;
        }

        .history-month-button:hover {
          background: #f9fafb;
        }

        .history-month-button:disabled {
          opacity: .5;
          cursor: not-allowed;
        }

        .history-legend {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          margin-bottom: 18px;
          padding: 12px 14px;
          border: 1px solid #eaecf0;
          border-radius: 10px;
          background: #f9fafb;
        }

        .history-legend-item {
          display: flex;
          align-items: center;
          gap: 7px;
          color: #475467;
          font-size: 11px;
          font-weight: 650;
        }

        .history-legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          display: inline-block;
          border: 1px solid rgba(16,24,40,.08);
        }

        .history-calendar {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          gap: 7px;
        }

        .history-weekday {
          text-align: center;
          padding: 9px 4px;
          color: #667085;
          font-size: 10px;
          font-weight: 750;
          text-transform: uppercase;
          letter-spacing: .5px;
        }

        .history-day {
          min-height: 86px;
          border: 1px solid #eaecf0;
          border-radius: 10px;
          padding: 9px;
          text-align: left;
          transition: .15s ease;
          position: relative;
          overflow: hidden;
        }

        .history-day:hover {
          transform: translateY(-1px);
          box-shadow: 0 3px 10px rgba(16,24,40,.08);
        }

        .history-day-empty {
          background: transparent;
          border-color: transparent;
          box-shadow: none;
        }

        .history-day-number {
          font-size: 14px;
          font-weight: 800;
          color: #101828;
        }

        .history-day-status {
          margin-top: 7px;
          font-size: 9px;
          font-weight: 750;
          text-transform: uppercase;
          letter-spacing: .2px;
        }

        .history-day-hours {
          margin-top: 5px;
          font-size: 10px;
          font-weight: 700;
          color: #344054;
        }

        .history-full-day {
          background: #ecfdf3;
          border-color: #abefc6;
          color: #067647;
        }

        .history-half-day {
          background: #fffaeb;
          border-color: #fedf89;
          color: #b54708;
        }

        .history-leave {
          background: #eff8ff;
          border-color: #b2ddff;
          color: #175cd3;
        }

        .history-absent {
          background: #fef3f2;
          border-color: #fecdca;
          color: #b42318;
        }

        .history-weekend {
          background: #f2f4f7;
          border-color: #d0d5dd;
          color: #667085;
        }

        .history-day-selected {
          outline: 3px solid #c7d2fe;
          outline-offset: 1px;
        }

        .history-details {
          margin-top: 22px;
          border: 1px solid #eaecf0;
          border-radius: 12px;
          padding: 18px;
          background: white;
        }

        .history-details-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 15px;
          padding-bottom: 15px;
          border-bottom: 1px solid #f2f4f7;
        }

        .history-summary-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          margin-top: 15px;
        }

        .history-summary-card {
          background: #f9fafb;
          border: 1px solid #eaecf0;
          border-radius: 9px;
          padding: 12px;
        }

        .history-summary-value {
          margin-top: 6px;
          color: #101828;
          font-size: 14px;
          font-weight: 750;
        }

        .history-detail-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          margin-top: 10px;
        }

        .history-detail-panel {
          border: 1px solid #eaecf0;
          border-radius: 9px;
          padding: 12px;
        }

        .history-reason {
          margin-top: 10px;
          padding: 12px;
          border-radius: 9px;
          background: #f9fafb;
          border: 1px solid #eaecf0;
        }

        .history-events-section {
          margin-top: 18px;
          padding-top: 16px;
          border-top: 1px solid #f2f4f7;
        }

        .history-event-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 0;
          border-bottom: 1px solid #f2f4f7;
          color: #344054;
        }

        .history-event-row:last-child {
          border-bottom: 0;
        }

        .history-event-time {
          margin-top: 4px;
          font-size: 13px;
          font-weight: 700;
          color: #101828;
        }

        .history-no-events {
          margin-top: 10px;
          padding: 12px;
          color: #98a2b3;
          background: #f9fafb;
          border-radius: 8px;
          font-size: 11px;
        }

        @media (max-width: 700px) {
          .capture-layout {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 1100px) {
          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .employee-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 800px) {
          .sidebar {
            width: 70px;
            padding: 20px 10px;
          }

          .brand {
            justify-content: center;
            padding-left: 0;
            padding-right: 0;
          }

          .brand-text,
          .nav-title,
          .nav-label,
          .sidebar-footer {
            display: none;
          }

          .nav-item {
            justify-content: center;
          }

          .main {
            width: calc(100% - 70px);
            margin-left: 70px;
          }

          .content {
            padding: 20px;
          }

          .topbar {
            padding: 0 20px;
          }

          .camera-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 600px) {
          .history-modal-body {
            padding: 14px;
          }

          .history-day {
            min-height: 68px;
            padding: 6px;
          }

          .history-day-number {
            font-size: 12px;
          }

          .history-day-status {
            font-size: 7px;
            margin-top: 5px;
          }

          .history-day-hours {
            font-size: 8px;
          }

          .history-summary-grid,
          .history-detail-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .report-chooser-grid {
            grid-template-columns: 1fr;
          }

          .stats-grid,
          .employee-grid {
            grid-template-columns: 1fr;
          }

          .page-heading {
            flex-direction: column;
            gap: 15px;
          }

          .form-grid {
            grid-template-columns: 1fr;
          }

          .form-group.full {
            grid-column: auto;
          }

          .system-status {
            display: none;
          }
        }
      `}</style>

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">F</div>

          <div className="brand-text">
            <div className="brand-title">FaceAttend</div>
            <div className="brand-subtitle">Attendance System</div>
          </div>
        </div>

        <div className="nav-title">Workspace</div>

        <button
          className={`nav-item ${
            activePage === "dashboard" ? "active" : ""
          }`}
          onClick={() => setActivePage("dashboard")}
        >
          <span className="nav-icon">⌂</span>
          <span className="nav-label">Dashboard</span>
        </button>

        <button
          className={`nav-item ${
            activePage === "employees" ? "active" : ""
          }`}
          onClick={() => setActivePage("employees")}
        >
          <span className="nav-icon">◉</span>
          <span className="nav-label">Employees</span>
        </button>

        <button
          className={`nav-item ${
            activePage === "attendance" ? "active" : ""
          }`}
          onClick={() => setActivePage("attendance")}
        >
          <span className="nav-icon">▣</span>
          <span className="nav-label">Attendance</span>
        </button>

        <div className="sidebar-footer">
          Face recognition attendance
          <br />
          Two-camera architecture
          <br />
          <span>v1.0</span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace /{" "}
            <strong style={{ color: "#344054" }}>
              {activePage === "dashboard"
                ? "Dashboard"
                : activePage === "employees"
                ? "Employees"
                : "Attendance"}
            </strong>
          </div>

          <div className="topbar-right">
            <div className="system-status">
              <span className="online-dot"></span>
              System Online
            </div>

            <button
              className="refresh-button"
              onClick={() => {
                if (activePage === "attendance") {
                  loadAttendanceByDate(selectedDate);
                  loadCameraStatus();
                } else {
                  loadDashboardData();
                  loadCameraStatus();
                }
              }}
            >
              ↻ Refresh
            </button>
          </div>
        </header>

        <div className="content">
          {activePage === "dashboard" && (
            <>
              <div className="page-heading">
                <div>
                  <h1 className="page-title">Attendance Dashboard</h1>
                  <p className="page-description">{todayText}</p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => setShowAddEmployee(true)}
                >
                  + Add Employee
                </button>
              </div>

              {error && (
                <div className="message error-message">
                  {error}
                </div>
              )}

              <div className="stats-grid">
                <div className="stat-card">
                  <div>
                    <div className="stat-label">Total Employees</div>
                    <div className="stat-value">{totalEmployees}</div>
                  </div>
                  <div className="stat-icon">◉</div>
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-label">Present Today</div>
                    <div className="stat-value">{presentToday}</div>
                  </div>
                  <div className="stat-icon">✓</div>
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-label">Late Today</div>
                    <div className="stat-value">{lateToday}</div>
                  </div>
                  <div className="stat-icon">!</div>
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-label">Currently Inside</div>
                    <div className="stat-value">{insideNow}</div>
                  </div>
                  <div className="stat-icon">↗</div>
                </div>
              </div>

              <section className="section">
                <div className="section-header">
                  <div>
                    <div className="section-title">Camera Monitoring</div>
                    <div className="section-caption">
                      Fixed cameras assigned to entry and exit points
                    </div>
                  </div>
                </div>

                {cameraError && (
                  <div className="message error-message">
                    {cameraError}
                  </div>
                )}

                <div className="camera-grid">
                  <CameraCard
                    title="Entry Camera"
                    responsibility="Employee check-in / IN detection"
                    camera={entryCamera}
                    loading={cameraLoading}
                  />

                  <CameraCard
                    title="Exit Camera"
                    responsibility="Employee check-out / OUT detection"
                    camera={exitCamera}
                    loading={cameraLoading}
                  />
                </div>
              </section>

              <AttendanceTable
                employees={filteredEmployees}
                getAttendance={getAttendance}
                getStatus={getStatus}
                formatStatus={formatStatus}
                formatTime={formatTime}
                formatWorkedTime={formatWorkedTime}
                statusClass={statusClass}
                search={search}
                setSearch={setSearch}
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
                loading={loading}
              />
            </>
          )}

          {activePage === "employees" && (
            <>
              <div className="page-heading">
                <div>
                  <h1 className="page-title">Employees</h1>
                  <p className="page-description">
                    Manage employees registered in the attendance system.
                  </p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => setShowAddEmployee(true)}
                >
                  + Add Employee
                </button>
              </div>

              <div className="page-panel">
                <div className="employee-grid">
                  {employees.map((employee) => {
                    const record = getAttendance(employee.employee_id);
                    const status = getStatus(record);

                    return (
                      <div
                        className="employee-card"
                        key={employee.employee_id}
                      >
                        <div className="employee-card-top">
                          <div className="employee-cell">
                            <div className="avatar">
                              {String(employee.employee_name || "E")
                                .charAt(0)
                                .toUpperCase()}
                            </div>

                            <div>
                              <div className="employee-card-name">
                                {employee.employee_name}
                              </div>

                              <div className="employee-card-id">
                                ID: {employee.employee_id}
                              </div>
                            </div>
                          </div>

                          <span
                            className={`status-badge ${statusClass(status)}`}
                          >
                            {formatStatus(status)}
                          </span>
                        </div>

                        <div className="employee-info">
                          <div className="info-row">
                            <span>Shift</span>
                            <span>
                              {employee.shift_start || "--"} -{" "}
                              {employee.shift_end || "--"}
                            </span>
                          </div>

                          <div className="info-row">
                            <span>Email</span>
                            <span>{employee.email || "--"}</span>
                          </div>

                          <div className="info-row">
                            <span>First In</span>
                            <span>
                              {formatTime(record?.first_in)}
                            </span>
                          </div>

                          <div className="info-row">
                            <span>Last Out</span>
                            <span>
                              {formatTime(record?.last_out)}
                            </span>
                          </div>

                          <div className="info-row">
                            <span>Worked</span>
                            <span>{formatWorkedTime(record)}</span>
                          </div>
                        </div>

                        <div
                          style={{
                            marginTop: 15,
                            display: "flex",
                            alignItems: "center",
                            gap: 12,
                            flexWrap: "wrap",
                          }}
                        >
                          <button
                            className="action-button"
                            onClick={() => openEmployeeHistory(employee)}
                          >
                            View attendance history →
                          </button>
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() => openEditShift(employee)}
                          >
                            Edit Shift
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {!employees.length && (
                  <div className="empty-state">
                    <div className="empty-icon">◉</div>
                    No employees registered.
                  </div>
                )}
              </div>
            </>
          )}

          {activePage === "attendance" && (
            <>
              <div className="page-heading">
                <div>
                  <h1 className="page-title">Attendance</h1>
                  <p className="page-description">
                    View employee attendance and working-time summary by date.
                  </p>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    flexWrap: "wrap",
                    justifyContent: "flex-end",
                  }}
                >
                  <button
                    className="primary-button"
                    onClick={openAllEmployeesReportChooser}
                  >
                    ↓ Download Excel
                  </button>

                  <label
                    style={{
                      fontSize: 12,
                      fontWeight: 650,
                      color: "#344054",
                    }}
                  >
                    Select Date
                  </label>

                  <input
                    type="date"
                    value={selectedDate}
                    onChange={handleAttendanceDateChange}
                    style={{
                      border: "1px solid #d0d5dd",
                      borderRadius: 8,
                      padding: "9px 11px",
                      color: "#344054",
                      outline: "none",
                      background: "white",
                      fontSize: 12,
                    }}
                  />
                </div>
              </div>

              {dateAttendanceError && (
                <div className="message error-message">
                  {dateAttendanceError}
                </div>
              )}

              <div
                style={{
                  marginBottom: 16,
                  padding: "12px 14px",
                  background: "#f9fafb",
                  border: "1px solid #eaecf0",
                  borderRadius: 8,
                  color: "#667085",
                  fontSize: 12,
                }}
              >
                Showing attendance for{" "}
                <strong style={{ color: "#344054" }}>
                  {selectedDateText}
                </strong>
              </div>

              <AttendanceTable
                employees={filteredEmployees}
                getAttendance={getAttendance}
                getStatus={getStatus}
                formatStatus={formatStatus}
                formatTime={formatTime}
                formatWorkedTime={formatWorkedTime}
                statusClass={statusClass}
                search={search}
                setSearch={setSearch}
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
                loading={dateAttendanceLoading}
                tableTitle={`Attendance — ${selectedDate}`}
                tableCaption="Historical event-based attendance and working-time summary"
              />
            </>
          )}
        </div>
      </main>

      {editingEmployee && (
        <div
          className="modal-backdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget && !editShiftLoading) {
              setEditingEmployee(null);
              setEditShiftError("");
            }
          }}
        >
          <div className="modal" style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <div>
                <h2 className="modal-title">Edit Employee Shift</h2>
                <div className="modal-subtitle">
                  {editingEmployee.employee_name} · ID: {editingEmployee.employee_id}
                </div>
              </div>
              <button
                type="button"
                className="close-button"
                onClick={() => {
                  if (!editShiftLoading) {
                    setEditingEmployee(null);
                    setEditShiftError("");
                  }
                }}
                disabled={editShiftLoading}
              >
                ×
              </button>
            </div>

            <form onSubmit={saveEmployeeShift}>
              <div style={{ padding: "20px" }}>
                {editShiftError && (
                  <div className="message error-message" style={{ marginBottom: 16 }}>
                    {editShiftError}
                  </div>
                )}
                <div className="form-group" style={{ marginBottom: 16 }}>
                  <label htmlFor="edit-shift-start">Shift Start</label>
                  <input
                    id="edit-shift-start"
                    type="time"
                    required
                    value={editShiftForm.shift_start}
                    disabled={editShiftLoading}
                    onChange={(event) => setEditShiftForm((previous) => ({
                      ...previous,
                      shift_start: event.target.value,
                    }))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="edit-shift-end">Shift End</label>
                  <input
                    id="edit-shift-end"
                    type="time"
                    required
                    value={editShiftForm.shift_end}
                    disabled={editShiftLoading}
                    onChange={(event) => setEditShiftForm((previous) => ({
                      ...previous,
                      shift_end: event.target.value,
                    }))}
                  />
                </div>
                <p style={{ color: "#667085", fontSize: 12, marginTop: 12 }}>
                  Overnight shifts are supported (for example, 16:00–01:00).
                </p>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    setEditingEmployee(null);
                    setEditShiftError("");
                  }}
                  disabled={editShiftLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={editShiftLoading}
                >
                  {editShiftLoading ? "Saving..." : "Save Shift"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAddEmployee && (
        <div
          className="modal-backdrop"
          onClick={(event) => {
            if (
              event.target === event.currentTarget &&
              !enrollmentLoading
            ) {
              closeAddEmployee();
            }
          }}
        >
          <div className="modal">
            <div className="modal-header">
              <div>
                <h2 className="modal-title">Add Employee</h2>
                <div className="modal-subtitle">
                  Add employee details and capture face photos for recognition.
                </div>
              </div>

              <button
                className="close-button"
                onClick={closeAddEmployee}
                disabled={enrollmentLoading}
              >
                ×
              </button>
            </div>

            <form onSubmit={addEmployee}>
              <div className="modal-body">
                {formError && (
                  <div className="message error-message">
                    {formError}
                  </div>
                )}

                {formMessage && (
                  <div className="message success-message">
                    {formMessage}
                  </div>
                )}

                <div className="form-grid">
                  <div className="form-group">
                    <label>Login ID</label>
                    <input
                      name="login_id"
                      value={employeeForm.login_id}
                      onChange={handleEmployeeFormChange}
                      placeholder="e.g. mbhasyam"
                      required
                      disabled={enrollmentLoading}
                    />
                  </div>

                  <div className="form-group">
                    <label>Shift Start</label>
                    <input
                      type="time"
                      name="shift_start"
                      value={employeeForm.shift_start}
                      onChange={handleEmployeeFormChange}
                      required
                      disabled={enrollmentLoading}
                    />
                  </div>

                  <div className="form-group">
                    <label>Shift End</label>
                    <input
                      type="time"
                      name="shift_end"
                      value={employeeForm.shift_end}
                      onChange={handleEmployeeFormChange}
                      required
                      disabled={enrollmentLoading}
                    />
                  </div>

                </div>

                <div className="enrollment-section">
                  <div className="enrollment-header">
                    <div>
                      <div className="enrollment-title">
                        Face Enrollment
                      </div>
                      <div className="enrollment-caption">
                        Capture 5–10 clear photos. Keep only the employee
                        in the frame.
                      </div>
                    </div>

                    <div className="capture-count">
                      {capturedPhotos.length} / 10 photos
                    </div>
                  </div>

                  {captureError && (
                    <div className="message error-message">
                      {captureError}
                    </div>
                  )}

                  <div className="capture-layout">
                    <div>
                      <div className="camera-preview">
                        {cameraStream ? (
                          <video
                            ref={videoRef}
                            autoPlay
                            muted
                            playsInline
                          />
                        ) : (
                          <div className="camera-placeholder">
                            Camera is not started.
                            <br />
                            Click “Start Camera” to begin.
                          </div>
                        )}
                      </div>

                      <canvas
                        ref={canvasRef}
                        style={{ display: "none" }}
                      />

                      <div className="capture-controls">
                        {!cameraStream ? (
                          <button
                            type="button"
                            className="camera-start-button"
                            onClick={startEnrollmentCamera}
                            disabled={enrollmentLoading}
                          >
                            Start Camera
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="capture-button"
                              onClick={captureSnapshot}
                              disabled={
                                enrollmentLoading ||
                                capturedPhotos.length >= 10
                              }
                            >
                              📷 Capture Snapshot
                            </button>

                            <button
                              type="button"
                              className="camera-start-button"
                              onClick={stopEnrollmentCamera}
                              disabled={enrollmentLoading}
                            >
                              Stop Camera
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    <div>
                      {capturedPhotos.length > 0 ? (
                        <div className="photo-grid">
                          {capturedPhotos.map((photo, index) => (
                            <div
                              className="photo-card"
                              key={`${photo.filename}-${index}`}
                            >
                              <img
                                src={photo.previewUrl}
                                alt={`Captured face ${index + 1}`}
                              />

                              <button
                                type="button"
                                className="remove-photo"
                                onClick={() =>
                                  removeCapturedPhoto(index)
                                }
                                disabled={enrollmentLoading}
                                title="Remove photo"
                              >
                                ×
                              </button>

                              <span className="photo-number">
                                {index + 1}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="capture-help">
                          <strong>Capture tips</strong>
                          <br />
                          • Look directly at the camera.
                          <br />
                          • Keep your whole face visible.
                          <br />
                          • Avoid multiple people in the frame.
                          <br />
                          • Capture slightly different angles.
                          <br />
                          • Minimum 5 photos required.
                          <br />
                          • Maximum 10 photos allowed.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={closeAddEmployee}
                  disabled={enrollmentLoading}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={
                    enrollmentLoading ||
                    capturedPhotos.length < 5
                  }
                >
                  {enrollmentLoading
                    ? "Enrolling Face..."
                    : "Save Employee & Enroll Face"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {reportChooser && (
        <div
          className="modal-backdrop report-chooser-backdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeReportChooser();
            }
          }}
        >
          <div className="report-chooser-modal">
            <div className="modal-header">
              <div>
                <h2 className="modal-title">Download Excel Report</h2>
                <div className="modal-subtitle">
                  Choose a {reportChooser.type === "employee" ? "weekly or monthly report for this employee" : "weekly or monthly report for all employees"}.
                </div>
              </div>

              <button
                className="close-button"
                onClick={closeReportChooser}
                disabled={reportDownloading}
                aria-label="Close report chooser"
              >
                ×
              </button>
            </div>

            <div className="modal-body">
              {reportError && (
                <div className="message error-message">
                  {reportError}
                </div>
              )}

              <div className="report-chooser-grid">
                <button
                  className="report-option"
                  onClick={() => downloadAttendanceReport("weekly")}
                  disabled={reportDownloading}
                >
                  <span className="report-option-icon">W</span>
                  <span>
                    <strong>Weekly Report</strong>
                    <small>Monday to Sunday, based on the selected date</small>
                  </span>
                </button>

                <button
                  className="report-option"
                  onClick={() => downloadAttendanceReport("monthly")}
                  disabled={reportDownloading}
                >
                  <span className="report-option-icon">M</span>
                  <span>
                    <strong>Monthly Report</strong>
                    <small>Full calendar month based on the selected date</small>
                  </span>
                </button>
              </div>

              {reportDownloading && (
                <div className="report-download-status">
                  Preparing Excel report...
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {selectedEmployee && (
        <div
          className="modal-backdrop history-modal-backdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeHistory();
            }
          }}
        >
          <div className="history-modal">
            <div className="history-modal-header">
              <div>
                <h2 className="modal-title">
                  {selectedEmployee.employee_name}
                </h2>
                <div className="modal-subtitle">
                  Employee ID: {selectedEmployee.employee_id}
                  {selectedEmployee.email
                    ? ` • ${selectedEmployee.email}`
                    : ""}
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <button
                  className="primary-button report-download-button"
                  onClick={openEmployeeReportChooser}
                  disabled={historyLoading}
                >
                  ↓ Download Excel
                </button>

                <button
                  className="close-button"
                  onClick={closeHistory}
                  aria-label="Close attendance history"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="history-modal-body">
              <div className="history-toolbar">
                <button
                  className="history-month-button"
                  onClick={() => changeHistoryMonth(-1)}
                  disabled={historyLoading}
                >
                  ←
                </button>

                <div className="history-month-title">
                  {historyMonthTitle}
                </div>

                <button
                  className="history-month-button"
                  onClick={() => changeHistoryMonth(1)}
                  disabled={historyLoading}
                >
                  →
                </button>
              </div>

              <div className="history-legend">
                {[
                  ["FULL_DAY", "Full Day"],
                  ["HALF_DAY", "Half Day"],
                  ["LEAVE", "Leave"],
                  ["ABSENT", "Absent"],
                  ["WEEKEND", "Weekend"],
                ].map(([status, label]) => (
                  <div className="history-legend-item" key={status}>
                    <span
                      className={`history-legend-dot ${
                        getHistoryStatusMeta(status).className
                      }`}
                    />
                    {label}
                  </div>
                ))}
              </div>

              {historyError && (
                <div className="message error-message">
                  {historyError}
                </div>
              )}

              {historyLoading ? (
                <div className="empty-state">
                  Loading attendance calendar...
                </div>
              ) : (
                <div className="history-calendar">
                  {[
                    "Sun",
                    "Mon",
                    "Tue",
                    "Wed",
                    "Thu",
                    "Fri",
                    "Sat",
                  ].map((day) => (
                    <div
                      className="history-weekday"
                      key={day}
                    >
                      {day}
                    </div>
                  ))}

                  {getHistoryCalendarCells().map((day, index) => {
                    if (!day) {
                      return (
                        <div
                          className="history-day history-day-empty"
                          key={`empty-${index}`}
                        />
                      );
                    }

                    const meta = getHistoryStatusMeta(day.status);

                    return (
                      <button
                        type="button"
                        className={`history-day ${meta.className} ${
                          selectedHistoryDay?.date === day.date
                            ? "history-day-selected"
                            : ""
                        }`}
                        key={day.date}
                        onClick={() => setSelectedHistoryDay(day)}
                      >
                        <div className="history-day-number">
                          {new Date(
                            `${day.date}T00:00:00`
                          ).getDate()}
                        </div>

                        <div className="history-day-status">
                          {meta.label}
                        </div>

                        {day.worked_hours &&
                          day.worked_hours !== "0h 0m" && (
                            <div className="history-day-hours">
                              {day.worked_hours}
                            </div>
                          )}
                      </button>
                    );
                  })}
                </div>
              )}

              {!historyLoading && selectedHistoryDay && (
                <div className="history-details">
                  <div className="history-details-header">
                    <div>
                      <div className="section-title">
                        {selectedHistoryDay.date
                          ? new Date(
                              `${selectedHistoryDay.date}T00:00:00`
                            ).toLocaleDateString("en-IN", {
                              weekday: "long",
                              day: "2-digit",
                              month: "long",
                              year: "numeric",
                            })
                          : "Attendance Details"}
                      </div>

                      <div className="section-caption">
                        Detailed attendance information for the
                        selected day
                      </div>
                    </div>

                    <span
                      className={`status-badge ${
                        getHistoryStatusMeta(
                          selectedHistoryDay.status
                        ).className
                      }`}
                    >
                      {
                        getHistoryStatusMeta(
                          selectedHistoryDay.status
                        ).label
                      }
                    </span>
                  </div>

                  <div className="history-summary-grid">
                    <div className="history-summary-card">
                      <div className="detail-label">IN TIME</div>
                      <div className="history-summary-value">
                        {formatTime(selectedHistoryDay.first_in)}
                      </div>
                    </div>

                    <div className="history-summary-card">
                      <div className="detail-label">OUT TIME</div>
                      <div className="history-summary-value">
                        {formatTime(selectedHistoryDay.last_out)}
                      </div>
                    </div>

                    <div className="history-summary-card">
                      <div className="detail-label">
                        HOURS WORKED
                      </div>
                      <div className="history-summary-value">
                        {selectedHistoryDay.worked_hours ||
                          formatMinutes(
                            selectedHistoryDay.worked_minutes
                          )}
                      </div>
                    </div>

                    <div className="history-summary-card">
                      <div className="detail-label">ARRIVAL</div>
                      <div className="history-summary-value">
                        {selectedHistoryDay.arrival_status || "--"}
                      </div>
                    </div>
                  </div>

                  <div className="history-detail-grid">
                    <div className="history-detail-panel">
                      <div className="detail-label">SHIFT</div>
                      <div className="detail-value">
                        {selectedEmployee.shift_start || "--"} -{" "}
                        {selectedEmployee.shift_end || "--"}
                      </div>
                    </div>

                    <div className="history-detail-panel">
                      <div className="detail-label">LATE</div>
                      <div className="detail-value">
                        {formatMinutes(
                          selectedHistoryDay.late_minutes
                        )}
                      </div>
                    </div>

                    <div className="history-detail-panel">
                      <div className="detail-label">EARLY</div>
                      <div className="detail-value">
                        {formatMinutes(
                          selectedHistoryDay.early_minutes
                        )}
                      </div>
                    </div>

                    <div className="history-detail-panel">
                      <div className="detail-label">LEAVE TYPE</div>
                      <div className="detail-value">
                        {selectedHistoryDay.leave_type || "--"}
                      </div>
                    </div>
                  </div>

                  {selectedHistoryDay.reason && (
                    <div className="history-reason">
                      <div className="detail-label">
                        LEAVE / ATTENDANCE NOTE
                      </div>
                      <div className="detail-value">
                        {selectedHistoryDay.reason}
                      </div>
                    </div>
                  )}

                  <div className="history-events-section">
                    <div className="section-title">Work Sessions</div>

                    {Array.isArray(selectedHistoryDay.sessions) &&
                    selectedHistoryDay.sessions.length > 0 ? (
                      selectedHistoryDay.sessions.map(
                        (session, index) => (
                          <div
                            className="history-event-row"
                            key={`session-${index}`}
                          >
                            <div>
                              <div className="detail-label">
                                SESSION {index + 1}
                              </div>
                              <div className="history-event-time">
                                {formatTime(session.in_time)} →{" "}
                                {formatTime(session.out_time)}
                              </div>
                            </div>

                            <strong>
                              {session.worked_hours ||
                                formatMinutes(
                                  session.worked_minutes
                                )}
                            </strong>
                          </div>
                        )
                      )
                    ) : (
                      <div className="history-no-events">
                        No completed work sessions for this date.
                      </div>
                    )}
                  </div>

                  <div className="history-events-section">
                    <div className="section-title">
                      Attendance Events
                    </div>

                    {Array.isArray(selectedHistoryDay.events) &&
                    selectedHistoryDay.events.length > 0 ? (
                      selectedHistoryDay.events.map(
                        (event, index) => {
                          const eventType = String(
                            event.event_type || ""
                          ).toUpperCase();

                          return (
                            <div
                              className="history-event-row"
                              key={`event-${index}`}
                            >
                              <div>
                                <div className="detail-label">
                                  {eventType || "EVENT"}
                                </div>
                                <div className="history-event-time">
                                  {formatTime(event.event_time)}
                                </div>
                              </div>

                              <span
                                className={`event-type ${
                                  eventType === "IN"
                                    ? "event-in"
                                    : "event-out"
                                }`}
                              >
                                {eventType || "EVENT"}
                              </span>
                            </div>
                          );
                        }
                      )
                    ) : (
                      <div className="history-no-events">
                        No attendance events recorded.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CameraCard({
  title,
  responsibility,
  camera,
  loading,
}) {
  const connected = Boolean(
    camera?.connected || camera?.device_exists
  );

  return (
    <div className="camera-card">
      <div className="camera-header">
        <div>
          <div className="camera-name">{title}</div>
          <div className="camera-responsibility">
            {responsibility}
          </div>
        </div>

        {!loading && (
          <div
            className={`connection-badge ${
              connected ? "connected" : "disconnected"
            }`}
          >
            <span>●</span>
            {connected ? "CONNECTED" : "DISCONNECTED"}
          </div>
        )}
      </div>

      <div className="camera-details">
        <div>
          <div className="detail-label">Device</div>
          <div className="detail-value">
            {camera?.device || "--"}
          </div>
        </div>

        <div>
          <div className="detail-label">Mode</div>
          <div className="detail-value">
            {camera?.mode || (title.includes("Entry") ? "ENTRY" : "EXIT")}
          </div>
        </div>

        <div>
          <div className="detail-label">Purpose</div>
          <div className="detail-value">
            {title.includes("Entry") ? "Check-in" : "Check-out"}
          </div>
        </div>

        <div>
          <div className="detail-label">Recognition</div>
          <div className="detail-value">
            InsightFace
          </div>
        </div>
      </div>
    </div>
  );
}

function AttendanceTable({
  employees,
  getAttendance,
  getStatus,
  formatStatus,
  formatTime,
  formatWorkedTime,
  statusClass,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
  loading,
  tableTitle = "Today's Attendance",
  tableCaption = "Event-based attendance and working-time summary",
}) {
  const filters = [
    ["ALL", "All"],
    ["ABSENT", "Absent"],
    ["HALF_DAY", "Half Day"],
    ["FULL_DAY", "Full Day"],
    ["INSIDE", "Inside"],
    ["OUTSIDE", "Outside"],
  ];

  return (
    <section className="section">
      <div className="section-header">
        <div>
          <div className="section-title">{tableTitle}</div>
          <div className="section-caption">
            {tableCaption}
          </div>
        </div>
      </div>

      <div className="table-card">
        <div className="table-toolbar">
          <div className="search-box">
            <span className="search-icon">⌕</span>

            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search employee..."
            />
          </div>

          <div className="filter-group">
            {filters.map(([value, label]) => (
              <button
                key={value}
                className={`filter-button ${
                  statusFilter === value ? "active" : ""
                }`}
                onClick={() => setStatusFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>First In</th>
                <th>Arrival</th>
                <th>Worked</th>
                <th>Sessions</th>
                <th>Last Out</th>
                <th>State</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7">
                    <div className="empty-state">
                      Loading attendance...
                    </div>
                  </td>
                </tr>
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan="7">
                    <div className="empty-state">
                      <div className="empty-icon">◷</div>
                      No attendance records found.
                    </div>
                  </td>
                </tr>
              ) : (
                employees.map((employee) => {
                  const record = getAttendance(employee.employee_id);
                  const status = getStatus(record);

                  return (
                    <tr key={employee.employee_id}>
                      <td>
                        <div className="employee-cell">
                          <div className="avatar">
                            {String(employee.employee_name || "E")
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <div>
                            <div className="employee-name">
                              {employee.employee_name}
                            </div>

                            <div className="employee-id">
                              ID: {employee.employee_id}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td>{formatTime(record?.first_in)}</td>

                      <td>
                        <span
                          className={`status-badge ${statusClass(status)}`}
                        >
                          {formatStatus(status)}
                        </span>
                      </td>

                      <td>
                        <strong>
                          {formatWorkedTime(record)}
                        </strong>
                      </td>

                      <td>
                        {record?.session_count ??
                          record?.sessions?.length ??
                          0}
                      </td>

                      <td>{formatTime(record?.last_out)}</td>

                      <td>
                        <span
                          className={`status-badge ${statusClass(
                            String(
                              record?.current_state || "OUTSIDE"
                            ).toUpperCase()
                          )}`}
                        >
                          {String(
                            record?.current_state || "OUTSIDE"
                          ).toUpperCase()}
                        </span>
                      </td>

                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default App;