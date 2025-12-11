let fixedCols = Columns.fixedCols;
let allCols = Columns.allCols;
let customCols = Columns.customCols;
let colTypes = Columns.colTypes;
let currentEmpId = Employee.currentEmpId;
let isAdmin = false;
const defaultAvatar = Utils.defaultAvatar;

function getAge(dateStr) { return Utils.getAge(dateStr); }
function formatDateAndAge(dateStr) { return Utils.formatDateAndAge(dateStr); }
function resizeImage(file, maxSize, quality) { return Utils.resizeImage(file, maxSize, quality); }
function debounce(func, wait) { return Utils.debounce(func, wait); }
function escapeHtml(text) { return Utils.escapeHtml(text); }
function getVisibleColumns() { return Columns.getVisibleColumns(); }
function loadColumns() { Columns.loadColumns(); }
function buildTableHead() { Columns.buildTableHead(); }
function buildColumnList() { Columns.buildColumnList(); }
function loadGroups(selectId, selected) { Groups.loadGroups(selectId, selected); }
function showGroupFilter(th) { Groups.showGroupFilter(th); }
function addColumn() { Columns.addColumn(); }
function loadEmployees(search, prefix) { Employee.loadEmployees(search, prefix); }
function buildEmployeeRow(emp, prefix) { return Employee.buildEmployeeRow(emp, prefix); }
function applyUserFilters(search, group) { Employee.applyUserFilters(search, group); }
function createEmployee(data) { return Employee.createEmployee(data); }
function updateEmployee(data) { Employee.updateEmployee(data); }
function uploadPhoto(file) { Employee.uploadPhoto(file); }
function closeAndRefresh() { Employee.closeAndRefresh(); }
function deleteEmployee(id) { Employee.deleteEmployee(id); }
function getHealthInfo(emp) { return Health.getHealthInfo(emp); }
function isCurrentlyIll(emp) { return Health.isCurrentlyIll(emp); }
function parseVacation(vacationText) { return Vacation.parseVacation(vacationText); }
function formatVacation(startTime, startDate, endTime, endDate) { return Vacation.formatVacation(startTime, startDate, endTime, endDate); }
function showVacationHistory(history) { Vacation.showHistory(history); }
function showVacationHistoryFromButton(button) { Vacation.showHistoryFromButton(button); }
function showChangesHistoryModal(empId) { History.showChangesHistoryModal(empId); }
function loadChangesHistory(empId) { History.loadChangesHistory(empId); }
function loadRoommates(empId) { Roommates.loadRoommates(empId); }
function renderRoommates(empId, roommates) { Roommates.renderRoommates(empId, roommates); }
function loadEmployeeReports(empId, showButtons) { Roommates.loadEmployeeReports(empId, showButtons); }
function renderReports(empId, data, showButtons) { Roommates.renderReports(empId, data, showButtons); }
function markBedLinenReceived(empId, weekNum) { Roommates.markBedLinenReceived(empId, weekNum); }
function markBedLinenReceivedByPeriod(empId, periodId, periodLabel) { Roommates.markBedLinenReceivedByPeriod(empId, periodId, periodLabel); }
function importExcel() { Import.importExcel(); }
function performImport() { Import.performImport(); }
function showAdminModal(id) { Modals.showAdminModal(id); }

$(document).ready(function () {
    Columns.loadColumns();
    if ($('#admin_search').length || $('#admin_tableBody').length) {
        Init.initAdminPage();
    } else if ($('#user_search').length) {
        setTimeout(function() {
            Init.initUserPage();
        }, 50);
    }
});

