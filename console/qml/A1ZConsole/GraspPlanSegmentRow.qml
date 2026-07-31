pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var segmentData
    property bool lastRow: false

    implicitHeight: 38

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        visible: !root.lastRow
        color: root.theme.separator
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10

        Text {
            Layout.preferredWidth: 100
            text: root.segmentData.index + ". " + root.segmentData.type
            textFormat: Text.PlainText
            color: root.theme.text
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            text: "[" + root.segmentData.jointsDeg.join(", ") + "]"
            textFormat: Text.PlainText
            color: root.theme.secondaryText
            elide: Text.ElideRight
            font.family: "monospace"
            font.pixelSize: root.theme.typeCaption
        }

        Text {
            Layout.preferredWidth: 70
            text: Number(root.segmentData.timeoutS).toFixed(1) + " s"
            color: root.theme.tertiaryText
            horizontalAlignment: Text.AlignRight
            font.family: "monospace"
            font.pixelSize: root.theme.typeCaption
        }
    }
}
