import QtQuick

Rectangle {
    id: root

    required property var theme
    property int padding: theme.spacingL
    default property alias contentData: content.data

    radius: theme.radiusCard
    color: theme.card
    border.color: theme.border
    border.width: 1

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 2
        anchors.rightMargin: 2
        height: 1
        color: root.theme.glassHighlight
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
