import QtQuick
import QtQuick.Controls.Basic

SpinBox {
    id: root

    required property var theme

    implicitWidth: 128
    implicitHeight: 40
    leftPadding: 40
    rightPadding: 40
    focusPolicy: Qt.StrongFocus

    contentItem: TextInput {
        z: 2
        text: root.displayText
        color: root.enabled ? root.theme.text : root.theme.placeholderText
        selectionColor: root.theme.accentSoft
        selectedTextColor: root.theme.text
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        readOnly: !root.editable
        validator: root.validator
        inputMethodHints: Qt.ImhFormattedNumbersOnly
        font.family: root.theme.fontFamily
        font.pixelSize: root.theme.typeLabel
    }

    down.indicator: Rectangle {
        x: 0
        y: 0
        implicitWidth: 40
        implicitHeight: root.height
        radius: root.theme.radiusControl
        color: root.down.pressed ? root.theme.controlPressed
               : root.down.hovered ? root.theme.controlHover
                                   : "transparent"

        Text {
            anchors.centerIn: parent
            text: "−"
            color: root.enabled ? root.theme.text : root.theme.placeholderText
            font.family: root.theme.fontFamily
            font.pixelSize: 18
        }
    }

    up.indicator: Rectangle {
        x: root.width - width
        y: 0
        implicitWidth: 40
        implicitHeight: root.height
        radius: root.theme.radiusControl
        color: root.up.pressed ? root.theme.controlPressed
               : root.up.hovered ? root.theme.controlHover
                                 : "transparent"

        Text {
            anchors.centerIn: parent
            text: "+"
            color: root.enabled ? root.theme.text : root.theme.placeholderText
            font.family: root.theme.fontFamily
            font.pixelSize: 18
        }
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.theme.control
        border.color: root.activeFocus ? root.theme.accent : "transparent"
        border.width: root.activeFocus ? 2 : 0

        Rectangle {
            anchors.left: parent.left
            anchors.leftMargin: 40
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: 20
            color: root.theme.separatorStrong
        }

        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 40
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: 20
            color: root.theme.separatorStrong
        }
    }
}
