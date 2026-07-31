pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    property bool followTail: true

    function scrollToTail() {
        logView.positionViewAtEnd()
    }


    FontMetrics {
        id: logFontMetrics
        font.family: "monospace"
        font.pixelSize: root.theme.typeCaption
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 9

        RowLayout {
            Layout.fillWidth: true

            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("运行日志")
            }

            AppButton {
                theme: root.theme
                kind: "quiet"
                text: root.followTail ? qsTr("暂停跟随") : qsTr("跟随最新")
                onClicked: {
                    root.followTail = !root.followTail
                    if (root.followTail)
                        logTailTimer.restart()
                }
            }

            AppButton {
                theme: root.theme
                kind: "quiet"
                text: qsTr("清空")
                onClicked: root.controller.clearLogs()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            radius: root.theme.radiusControl
            color: root.theme.logCanvas
            border.width: 0

            ListView {
                id: logView
                anchors.fill: parent
                anchors.margins: 1
                clip: true
                // Keep collection in the controller, but detach the expensive
                // delegate view while this persistent page is hidden.
                model: root.visible ? root.controller.logModel : null
                currentIndex: -1
                reuseItems: true
                cacheBuffer: Math.max(0, height)
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.AutoFlickDirection
                contentWidth: Math.max(
                                  width,
                                  root.controller.logModel.maximumDisplayColumns
                                  * logFontMetrics.advanceWidth("M") + 20)
                Accessible.name: qsTr("运行日志")
                ScrollBar.horizontal: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }
                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }

                delegate: Text {
                    required property string line

                    width: logView.contentWidth
                    height: implicitHeight + 2
                    leftPadding: 10
                    rightPadding: 10
                    text: line
                    textFormat: Text.PlainText
                    color: root.theme.secondaryText
                    wrapMode: Text.NoWrap
                    font.family: "monospace"
                    font.pixelSize: root.theme.typeCaption
                }

                onCountChanged: {
                    if (root.visible && root.followTail)
                        logTailTimer.restart()
                }
            }

            Timer {
                id: logTailTimer
                interval: 0
                repeat: false
                onTriggered: root.scrollToTail()
            }
        }
    }
}
