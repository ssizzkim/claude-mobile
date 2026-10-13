Attribute VB_Name = "BankSort"
' Bank sort button: pick the downloaded files, banksort.py classifies them and matches tax invoices.
' Mac VBE mangles Hangul, so build.py turns U("116,101,120,116") markers into U("code,...") calls.
Option Explicit

Private Const SCRIPT_FILE As String = "banksort.scpt"

Private Function U(ByVal codes As String) As String
    Dim parts() As String, i As Long, s As String
    parts = Split(codes, ",")
    For i = LBound(parts) To UBound(parts)
        s = s & ChrW(CLng(parts(i)))
    Next i
    U = s
End Function

Private Function Bridge(ByVal handler As String, ByVal arg As String) As String
    On Error GoTo Fail
    Bridge = AppleScriptTask(SCRIPT_FILE, handler, arg)
    Exit Function
Fail:
    Bridge = "ERROR:" & U("50672,44208,32,49828,53356,47549,53944,47484,32,49892,54665,54616,51648,32,47803,54664,49845,45768,45796,46,32,49444,52824,32,47749,47161,40,98,97,110,107,45,115,111,114,116,47,105,110,115,116,97,108,108,46,115,104,41,51012,32,45796,49884,32,49892,54665,54616,49464,50836,46") & vbLf & Err.Description
End Function

Private Sub CloseTarget()
    ' Save and close the merged workbook if open (hand edits survive the rebuild).
    Dim names As String, wb As Workbook, i As Long, cand() As String
    names = Bridge("targetNames", "")
    If Left$(names, 6) = "ERROR:" Then Exit Sub
    cand = Split(names, vbLf)
    For i = Application.Workbooks.Count To 1 Step -1
        Set wb = Application.Workbooks(i)
        Dim j As Long
        For j = LBound(cand) To UBound(cand)
            If Len(cand(j)) > 0 And (wb.Name = cand(j) Or wb.FullName = cand(j)) Then
                If Not wb.Saved Then wb.Save
                wb.Close SaveChanges:=False
                Exit For
            End If
        Next j
    Next i
End Sub

Public Sub BankSortRun()
    Dim picked As Variant, paths As String, i As Long, res As String
    picked = Application.GetOpenFilename(Title:=U("51221,47532,54624,32,50641,49472,32,54028,51068,51012,32,47784,46160,32,44256,47476,49464,50836,32,40,49888,54620,32,51312,54924,183,51060,52404,44208,44284,44,32,54856,53469,49828,32,47588,52636,183,47588,51077,41"), MultiSelect:=True)
    If IsArray(picked) Then
        For i = LBound(picked) To UBound(picked)
            paths = paths & picked(i) & vbLf
        Next i
    ElseIf VarType(picked) = vbString Then
        paths = picked & vbLf
    Else
        Exit Sub
    End If
    RunWith paths
End Sub

Public Sub BankSortRebuild()
    ' Rebuild the merged workbook without new files.
    RunWith ""
End Sub

Private Sub RunWith(ByVal paths As String)
    Dim res As String, lines() As String, msg As String, target As String, i As Long
    CloseTarget
    Application.StatusBar = U("51008,54665,51221,47532,32,51473,46,46,46")
    Application.Cursor = xlWait
    res = Bridge("runBankSort", paths)
    Application.Cursor = xlDefault
    Application.StatusBar = False
    res = Replace(res, vbCr, vbLf)
    lines = Split(res, vbLf)
    For i = LBound(lines) To UBound(lines)
        If Left$(lines(i), 5) = "OPEN:" Then
            target = Mid$(lines(i), 6)
        ElseIf Left$(lines(i), 6) = "ERROR:" Then
            msg = msg & Mid$(lines(i), 7) & vbLf
        ElseIf Len(lines(i)) > 0 Then
            msg = msg & lines(i) & vbLf
        End If
    Next i
    If Len(target) > 0 Then
        On Error Resume Next
        Workbooks.Open target
        On Error GoTo 0
        MsgBox msg, vbInformation, U("51008,54665,51221,47532,32,50756,47308")
    Else
        MsgBox msg, vbExclamation, U("51008,54665,51221,47532,32,49892,54056")
    End If
End Sub

Public Sub SetupButton()
    Dim ws As Worksheet, shp As Shape, k As Long
    Set ws = ThisWorkbook.Worksheets(1)
    For k = ws.Shapes.Count To 1 Step -1
        ws.Shapes(k).Delete
    Next k
    Set shp = ws.Shapes.AddShape(msoShapeRoundedRectangle, ws.Range("B4").Left, ws.Range("B4").Top, 300, 64)
    shp.Name = "BankSortButton"
    shp.Fill.ForeColor.RGB = RGB(31, 78, 120)
    shp.Line.Visible = msoFalse
    With shp.TextFrame2
        .TextRange.Text = U("51008,54665,51221,47532,32,49892,54665")
        .TextRange.Font.Size = 20
        .TextRange.Font.Bold = msoTrue
        .TextRange.Font.Fill.ForeColor.RGB = RGB(255, 255, 255)
        .TextRange.ParagraphFormat.Alignment = msoAlignCenter
        .VerticalAnchor = msoAnchorMiddle
    End With
    shp.OnAction = "BankSortRun"
    Set shp = ws.Shapes.AddShape(msoShapeRoundedRectangle, ws.Range("B4").Left + 320, ws.Range("B4").Top, 200, 64)
    shp.Name = "BankSortRebuildButton"
    shp.Fill.ForeColor.RGB = RGB(242, 242, 242)
    shp.Line.ForeColor.RGB = RGB(166, 166, 166)
    With shp.TextFrame2
        .TextRange.Text = U("54028,51068,32,50630,51060,32,45796,49884,32,51221,47532")
        .TextRange.Font.Size = 14
        .TextRange.Font.Fill.ForeColor.RGB = RGB(64, 64, 64)
        .TextRange.ParagraphFormat.Alignment = msoAlignCenter
        .VerticalAnchor = msoAnchorMiddle
    End With
    shp.OnAction = "BankSortRebuild"
End Sub
