pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property string modeState
    required property bool freeDrive
    required property bool controlEnabled
    property bool draftPending: false
    readonly property bool stateConfirmed: root.modeState === "confirmed"

    signal modeRequested(bool freeDrive)

    implicitHeight: 150

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("夹爪交互模式")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                kind: root.stateConfirmed && !root.freeDrive
                      ? "selected" : "secondary"
                text: qsTr("开度控制")
                Accessible.role: Accessible.RadioButton
                Accessible.checked: root.stateConfirmed && !root.freeDrive
                enabled: root.controlEnabled
                         && root.freeDrive
                         && !root.draftPending
                onClicked: root.modeRequested(false)
            }

            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                kind: root.stateConfirmed && root.freeDrive
                      ? "selected" : "secondary"
                text: qsTr("自由拖动")
                Accessible.role: Accessible.RadioButton
                Accessible.checked: root.stateConfirmed && root.freeDrive
                enabled: root.controlEnabled
                         && !root.freeDrive
                         && !root.draftPending
                onClicked: root.modeRequested(true)
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.draftPending
                  ? qsTr("有未发送开度目标 · 模式切换已锁定")
                  : root.modeState === "pending"
                  ? qsTr("模式切换中 · 等待设备确认")
                  : root.modeState === "uncertain"
                  ? qsTr("模式结果不确定 · 请先核对现场并重新刷新")
                  : !root.stateConfirmed
                  ? root.freeDrive
                    ? qsTr("状态未确认 · 最后显示为自由拖动")
                    : qsTr("状态未确认 · 最后显示为开度控制")
                  : root.freeDrive
                    ? qsTr("当前为自由拖动；开度命令已锁定")
                    : qsTr("当前为开度控制；可调整目标并发送")
            color: root.draftPending
                   || root.freeDrive
                   || root.modeState === "uncertain"
                   ? root.theme.orange : root.theme.tertiaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }
    }
}
