import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root

    required property var theme
    property string text: ""
    property string level: "info"
    property bool dismissible: false
    signal dismissed()

    function announceIfCritical() {
        if (root.text.length > 0
                && (root.level === "error" || root.level === "warn")) {
            Accessible.announce(root.text)
        }
    }

    implicitHeight: text.length > 0 ? (level === "error" ? 64 : 42) : 0
    radius: theme.radiusControl
    color: level === "error" ? theme.redSoft
           : level === "warn" ? theme.orangeSoft
           : level === "success" ? theme.greenSoft
                              : theme.accentSoft
    Accessible.role: Accessible.AlertMessage
    Accessible.name: root.text
    Accessible.ignored: root.text.length === 0
    onTextChanged: Qt.callLater(root.announceIfCritical)

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            radius: 9
            color: root.level === "error" ? root.theme.red
                   : root.level === "warn" ? root.theme.orange
                   : root.level === "success" ? root.theme.green
                                          : root.theme.accent

            Text {
                anchors.centerIn: parent
                text: root.level === "error" ? "!"
                      : root.level === "success" ? "✓" : "i"
                color: root.theme.textOnAccent
                font.family: root.theme.fontFamily
                font.pixelSize: 11
                font.weight: Font.Bold
            }
        }

        Text {
            id: messageText

            Layout.fillWidth: true
            text: root.text
            textFormat: Text.PlainText
            color: root.level === "error" ? root.theme.red
                   : root.level === "success" ? root.theme.green
                   : root.theme.text
            wrapMode: root.level === "error" ? Text.WordWrap : Text.NoWrap
            maximumLineCount: root.level === "error" ? 2 : 1
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.Medium
            HoverHandler {
                id: messageHover
            }

            ToolTip {
                visible: messageHover.hovered && messageText.truncated

                contentItem: Text {
                    text: root.text
                    textFormat: Text.PlainText
                    color: root.theme.text
                    wrapMode: Text.Wrap
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }
            }
        }

        AppButton {
            Layout.preferredWidth: 32
            Layout.preferredHeight: 30
            visible: root.dismissible
            theme: root.theme
            kind: "quiet"
            text: qsTr("×")
            Accessible.name: qsTr("关闭操作反馈")
            onClicked: root.dismissed()
        }
    }
}
