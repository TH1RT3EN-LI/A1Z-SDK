import QtQuick

Rectangle {
    id: root

    required property var theme
    property int padding: theme.spacingL
    property bool outlined: false
    property color fillColor: theme.card
    default property alias contentData: content.data

    radius: theme.radiusCard
    color: fillColor
    border.color: outlined ? theme.border : "transparent"
    border.width: outlined ? 1 : 0

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
